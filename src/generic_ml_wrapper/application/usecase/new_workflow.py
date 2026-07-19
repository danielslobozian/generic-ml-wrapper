# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The NewWorkflow use case: author a workflow via the create-workflow interview."""

from __future__ import annotations

from collections.abc import Callable

from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.identifiers import IdentifierError, WorkflowName
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.hook_runner import HookRunner
from generic_ml_wrapper.application.domain.service.session_naming import next_session_id
from generic_ml_wrapper.application.port.inbound.new_workflow import (
    NewWorkflow,
    NewWorkflowCommand,
    NewWorkflowResult,
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
        self._store.record(session)

        draft = self._workflows.create_draft(session.session_id)
        run = RunContext(
            job=job,
            session_id=session.session_id,
            client=session.client,
            uuid=session.uuid,
            resume=False,
            cwd=draft,
            context=self._workflows.compile(CompileMode.AUTHORING, _META),
            kickoff=self._kickoff(command.name, draft),
        )
        caller = self._callers.for_run(run)
        exit_code = run_with_hooks(caller, run, self._hooks)
        return self._finalize(exit_code, draft)

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
    def _kickoff(name: str | None, draft: str) -> str:
        """The opening instruction: author in the draft, then leave a deploy marker."""
        suggested = (
            f"The user suggested the name {name!r}; confirm it or propose a better one. "
            if name is not None
            else "No name was given; propose one once the workflow has taken shape. "
        )
        return (
            "You are creating a new workflow. Your working directory is a private draft "
            f"folder ({draft}); do all your authoring there. " + suggested + "Follow the "
            "create-workflow steps: interview the user, then draft and save workflow.md in "
            "this folder. When it is ready, write a meta.json file here containing "
            '{"name": "<the-workflow-name>", "status": "finished"} so gmlw can deploy the '
            "draft to its final home. Start by asking what this workflow is for."
        )
