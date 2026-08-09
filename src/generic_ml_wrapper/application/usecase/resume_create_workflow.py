# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ResumeCreateWorkflowUseCase use case: carry on an unfinished interview."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from generic_ml_wrapper.application.domain.model.draft import Draft
from generic_ml_wrapper.application.domain.model.no_such_draft_error import NoSuchDraftError
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.port.inbound.create_workflow_result import CreateWorkflowResult
from generic_ml_wrapper.application.port.inbound.resume_create_workflow import (
    ResumeCreateWorkflowUseCase,
)
from generic_ml_wrapper.application.port.inbound.resume_create_workflow_command import (
    ResumeCreateWorkflowCommand,
)
from generic_ml_wrapper.application.port.outbound.cli_caller_provider import CliCallerProviderPort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.draft_deployment import settle_draft
from generic_ml_wrapper.application.usecase.launch import LaunchSequence

META = "create-workflow"


class ResumeCreateWorkflowService(ResumeCreateWorkflowUseCase):
    """Reopen an unfinished draft and carry on the interview that made it."""

    def __init__(
        self,
        workflows: WorkflowSourcePort,
        store: SessionStorePort,
        callers: CliCallerProviderPort,
        launch: LaunchSequence,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            workflows: Lists drafts, seeds the meta, and deploys a settled draft.
            store: Where the interview's session is read from.
            callers: Resolves the caller for the session's own client.
            launch: The bracketed launch sequence (hooks, metering, the client).
            clock: Returns "now" for a deployed folder's recorded creation time.
        """
        self._workflows = workflows
        self._store = store
        self._callers = callers
        self._launch = launch
        self._clock = clock

    def execute(self, command: ResumeCreateWorkflowCommand) -> CreateWorkflowResult:
        """Reopen the draft and carry on.

        The client is the session's own: the conversation belongs to the client that held
        it, and reopening it on another would start from nothing. No context is
        re-injected for the same reason — the client already has the interview in its
        history.

        Args:
            command: Names the draft, or asks for the latest unfinished one.

        Returns:
            The result: the client's exit code and how the draft resolved.

        Raises:
            NoSuchDraftError: When the draft is gone, nothing is resumable, its session
                was never recorded, or its client cannot reopen it.
        """
        self._workflows.seed()
        draft = self._target_draft(command.draft_key)
        run = self._run_for(draft)
        caller = self._callers.for_run(run)
        if not caller.can_resume():
            raise NoSuchDraftError(
                "error.draft.resume_unsupported",
                client=run.client,
                session_id=run.session_id,
            )
        return settle_draft(self._workflows, self._clock, self._launch.run(caller, run), draft.path)

    def _target_draft(self, draft_key: str | None) -> Draft:
        """The draft to reopen: the one named, else the most recent unfinished one.

        Args:
            draft_key: The draft named by the user, or ``None``.

        Returns:
            The draft to carry on with. A *finished* draft is skipped when picking the
            latest, because it is not waiting on the user — it converged and was blocked
            from deploying, and reopening it silently would hide that. Naming it
            explicitly still works, which is how a user fixes exactly that.

        Raises:
            NoSuchDraftError: When the named draft is gone, or nothing is unfinished.
        """
        drafts = self._workflows.drafts()
        if draft_key is not None:
            found = next((d for d in drafts if d.key == draft_key), None)
            if found is None:
                raise NoSuchDraftError("error.draft.not_found", key=draft_key)
            return found
        unfinished = next((d for d in drafts if not d.finished), None)
        if unfinished is None:
            raise NoSuchDraftError("error.draft.none_unfinished")
        return unfinished

    def _run_for(self, draft: Draft) -> RunContext:
        """Build the run that reopens the interview behind a draft.

        The draft folder is named after the authoring session that created it, so the
        session id is recovered from the folder rather than from anything stored — which
        is what lets drafts made before this existed be reopened too.

        Args:
            draft: The draft being carried on.

        Returns:
            A resuming run in the draft's own folder.

        Raises:
            NoSuchDraftError: When no session was ever recorded for that draft.
        """
        session = next(
            (s for s in self._store.sessions_for_job(META) if s.session_id == draft.key), None
        )
        if session is None:
            raise NoSuchDraftError("error.draft.no_session", key=draft.key)
        return RunContext(
            job=META,
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
