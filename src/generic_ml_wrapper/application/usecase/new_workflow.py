# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The NewWorkflow use case: author a workflow via the create-workflow interview."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.draft import Draft
from generic_ml_wrapper.application.domain.model.identifiers import IdentifierError, WorkflowName
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.domain.service.session_naming import next_session_id
from generic_ml_wrapper.application.port.inbound.new_workflow import (
    NewWorkflow,
    NewWorkflowCommand,
    NewWorkflowResult,
    NoSuchDraftError,
    WorkflowExistsError,
    WorkflowNameError,
    WorkflowOutcome,
)
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCallerProvider
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.launch import run_with_hooks

_META = "create-workflow"
_RESERVED = frozenset({_META, "_common"})


class NewWorkflowUseCase(NewWorkflow):
    """Author a workflow in a draft folder, then deploy it once the session names it.

    The name is decided at the end of the interview, not the start, so authoring runs
    in a scratch draft folder under the ``create-workflow`` job (sessions accumulate as
    ``create-workflow_NNN``). On convergence the session writes a marker naming the
    workflow; the use case then deploys the draft into ``workflows/<name>/``. A given
    name is only a seed — it lets a known name fail fast on a collision up front, but
    the final name still comes from the marker.
    """

    def __init__(
        self,
        workflows: WorkflowSourcePort,
        store: SessionStorePort,
        callers: CliCallerProvider,
        uuid_factory: Callable[[], str],
        hooks: HookRunner,
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            workflows: Seeds, checks, drafts, compiles, and deploys workflows.
            store: Records the authoring session.
            callers: Resolves the client caller for the run.
            uuid_factory: Mints a client-side session uuid.
            hooks: The lifecycle hooks bracketing the authoring client run.
        """
        self._workflows = workflows
        self._store = store
        self._callers = callers
        self._uuid_factory = uuid_factory
        self._hooks = hooks

    def execute(self, command: NewWorkflowCommand) -> NewWorkflowResult:
        """Run the authoring session for a new workflow and deploy its draft.

        Args:
            command: The request describing the (optional) name and the client.

        Returns:
            The result: the client's exit code and how the draft resolved.

        Raises:
            WorkflowNameError: If a given name is invalid or reserved.
            WorkflowExistsError: If a given name already exists (fail fast, up front).
        """
        self._workflows.seed()
        if command.resume_draft is not None or command.resume_latest:
            return self._reopen(command)
        if command.name is not None:  # a seed name lets a known collision fail fast
            self._validate(command.name)
            if self._workflows.exists(command.name):
                message = f"workflow already exists: {command.name!r}"
                raise WorkflowExistsError(message)

        # Authoring always runs under the create-workflow job (its store is rooted apart
        # from real work jobs), so sessions accumulate as create-workflow_NNN regardless
        # of the target name — which is not known until the session ends.
        job = _META
        session = Session(
            session_id=next_session_id(job, self._store.ids_for_job(job)),
            job=job,
            client=command.client,
            uuid=self._uuid_factory(),
        )
        draft = self._workflows.create_draft(session.session_id)
        run = RunContext(
            job=job,
            session_id=session.session_id,
            client=session.client,
            uuid=session.uuid,
            resume=False,
            cwd=draft,
            context=self._authoring_context(guided=command.guided, job=job),
            kickoff=self._kickoff(command.name, draft, guided=command.guided),
        )
        caller = self._callers.for_run(run)
        # Record where it ran and whether its caller can reopen it. Both were previously
        # left unset, which is what made an interrupted interview unrecoverable: the
        # session claimed a folder it had not stored, on a client nobody had asked.
        self._store.record(replace(session, cwd=draft, resumable=caller.can_resume()))
        exit_code = run_with_hooks(caller, run, self._hooks)
        return self._finalize(exit_code, draft)

    def _reopen(self, command: NewWorkflowCommand) -> NewWorkflowResult:
        """Reopen an unfinished draft and carry on the interview that made it.

        The draft folder is named after the authoring session that created it, so the
        session id is recovered from the folder rather than from anything we stored —
        which is what lets drafts made before this existed be reopened too.

        The client is the session's own, not the command's: the conversation belongs to
        the client that held it, and reopening it on another one would start from
        nothing. No context is re-injected for the same reason — the client already has
        the interview in its history, and re-sending it would talk over that.

        Raises:
            NoSuchDraftError: If the named draft is gone, nothing is resumable, or the
                session behind it was never recorded.
        """
        draft = self._target_draft(command)
        session = next(
            (s for s in self._store.sessions_for_job(_META) if s.session_id == draft.key), None
        )
        if session is None:
            message = f"draft {draft.key!r} has no recorded session to resume"
            raise NoSuchDraftError(message)
        run = RunContext(
            job=_META,
            session_id=session.session_id,
            client=session.client,
            uuid=session.uuid,
            resume=True,
            cwd=draft.path,
            kickoff=(
                "You are picking up an unfinished create-workflow interview. Your draft "
                f"folder is {draft.path} and your earlier work is there. Take stock of "
                "where it stands, tell me, then carry on from that point — do not start over."
            ),
        )
        caller = self._callers.for_run(run)
        if not caller.can_resume():
            message = f"{session.client} cannot reopen {session.session_id}"
            raise NoSuchDraftError(message)
        exit_code = run_with_hooks(caller, run, self._hooks)
        return self._finalize(exit_code, draft.path)

    def _target_draft(self, command: NewWorkflowCommand) -> Draft:
        """The draft to reopen: the one named, else the most recent unfinished one.

        A *finished* draft is skipped by ``--resume-latest`` because it is not waiting on
        the user — it converged and was blocked from deploying (its name was taken, or
        unusable), and reopening it silently would hide that. Naming it explicitly still
        works, which is how a user fixes exactly that.
        """
        drafts = self._workflows.drafts()
        if command.resume_draft is not None:
            found = next((d for d in drafts if d.key == command.resume_draft), None)
            if found is None:
                message = f"no such draft: {command.resume_draft!r}"
                raise NoSuchDraftError(message)
            return found
        unfinished = next((d for d in drafts if not d.finished), None)
        if unfinished is None:
            message = "no unfinished draft to resume"
            raise NoSuchDraftError(message)
        return unfinished

    def _finalize(self, exit_code: int, draft: str) -> NewWorkflowResult:
        """Deploy the draft if the session named it and declared it finished.

        A missing/unfinished marker, an unusable proposed name, or a name already taken
        each leaves the draft in place (nothing is lost); only a finished, valid, free
        name is deployed into ``workflows/<name>/``.
        """
        marker = self._workflows.read_draft_marker(draft)
        if not marker.finished or marker.name is None:
            return NewWorkflowResult(exit_code, WorkflowOutcome.INCOMPLETE, marker.name, draft)
        try:
            self._validate(marker.name)
        except WorkflowNameError:  # the session proposed an unusable name — keep the draft
            return NewWorkflowResult(exit_code, WorkflowOutcome.INCOMPLETE, marker.name, draft)
        if self._workflows.exists(marker.name):
            return NewWorkflowResult(exit_code, WorkflowOutcome.COLLISION, marker.name, draft)
        deployed = self._workflows.deploy_draft(draft, marker.name)
        return NewWorkflowResult(exit_code, WorkflowOutcome.DEPLOYED, marker.name, deployed)

    def _authoring_context(self, *, guided: bool, job: str) -> str:
        """The authoring context, with the guided-facilitation layer added when chosen."""
        context = self._workflows.compile(CompileMode.AUTHORING, _META, job=job)
        if not guided:
            return context
        guide = self._workflows.meta_guide()
        return f"{context}\n\n\n{guide}" if guide else context

    @staticmethod
    def _validate(name: str) -> None:
        """Reject an invalid or reserved workflow name."""
        try:
            WorkflowName(name)
        except IdentifierError as error:
            raise WorkflowNameError(str(error)) from error
        if name in _RESERVED:
            message = f"reserved workflow name: {name!r}"
            raise WorkflowNameError(message)

    @staticmethod
    def _kickoff(name: str | None, draft: str, *, guided: bool) -> str:
        """The opening instruction: author in the draft, then leave a deploy marker."""
        suggested = (
            f"The user suggested the name {name!r}; confirm it or propose a better one. "
            if name is not None
            else "No name was given; propose one once the workflow has taken shape. "
        )
        guide = (
            "Guided facilitation is on — follow the guided layer in your context, and keep "
            "a draft.md and a parking-lot.md in this folder as you go. "
            if guided
            else ""
        )
        return (
            "You are creating a new workflow. Your working directory is a private draft "
            f"folder ({draft}); do all your authoring there. " + suggested + guide + "Follow "
            "the create-workflow steps: interview the user, then draft and save workflow.md "
            "in this folder. When it is ready, write a meta.json file here containing "
            '{"name": "<the-workflow-name>", "status": "finished"} so gmlw can deploy the '
            "draft to its final home. Start by asking what this workflow is for."
        )
