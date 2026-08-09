# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The EditWorkflowUseCase use case: open an existing workflow in an authoring session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from generic_ml_wrapper.application.domain.model.authoring_job import AuthoringJob
from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.service.session_naming import SessionNaming
from generic_ml_wrapper.application.port.inbound.edit_workflow import EditWorkflowUseCase
from generic_ml_wrapper.application.port.inbound.edit_workflow_command import EditWorkflowCommand
from generic_ml_wrapper.application.port.outbound.cli_caller_provider import CliCallerProviderPort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.launch import LaunchSequence
from generic_ml_wrapper.application.usecase.workflow_folder import META, folder_for_editing


class EditWorkflowService(EditWorkflowUseCase):
    """Open an existing workflow's folder and run the authoring session against it."""

    def __init__(
        self,
        workflows: WorkflowSourcePort,
        store: SessionStorePort,
        callers: CliCallerProviderPort,
        uuid_factory: Callable[[], str],
        launch: LaunchSequence,
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            workflows: Seeds, checks, and locates workflows (never creates here).
            store: Records the authoring session.
            callers: Resolves the client caller for the run.
            uuid_factory: Mints a client-side session uuid.
            launch: The bracketed launch sequence (hooks, metering, the client).
        """
        self._workflows = workflows
        self._store = store
        self._callers = callers
        self._uuid_factory = uuid_factory
        self._launch = launch

    def execute(self, command: EditWorkflowCommand) -> int:
        """Run the authoring session against an existing workflow.

        Args:
            command: The request describing the workflow name and client.

        Returns:
            The client's exit code.

        Raises:
            WorkflowNameError: If the name is invalid or reserved.
            WorkflowNotFoundError: If no workflow with that name exists.
        """
        name = command.name
        folder = folder_for_editing(self._workflows, name)
        # Editing files under the same job as creating: authoring is one history, whatever
        # workflow it touches, and one name is all the job listing has to leave out. Which
        # workflow a session edited is told by its folder, not by the job it is filed under.
        job = AuthoringJob.NAME
        session = Session(
            session_id=SessionNaming().next_session_id(job, self._store.ids_for_job(job)),
            job=job,
            client=command.client,
            uuid=self._uuid_factory(),
        )

        guide = (
            "Guided facilitation is on — follow the guided layer in your context. "
            if command.guided
            else ""
        )
        run = RunContext(
            job=job,
            session_id=session.session_id,
            client=session.client,
            uuid=session.uuid,
            resume=False,
            cwd=folder,
            context=self._authoring_context(guided=command.guided, job=job),
            kickoff=(
                f"You are editing the existing workflow {name!r}. Your working directory "
                f"is its folder ({folder}); its current workflow.md is there. Read it "
                "first, then ask me what I want to change before editing. " + guide + "Do "
                "not rewrite it from scratch — amend it."
            ),
        )
        caller = self._callers.for_run(run)
        # Record where it ran and whether its caller can reopen it — both previously
        # unset, which left an interrupted edit with no folder to return to and no
        # capability recorded, however able its client was.
        self._store.record(replace(session, cwd=folder, resumable=caller.can_resume()))
        return self._launch.run(caller, run)

    def _authoring_context(self, *, guided: bool, job: str) -> str:
        """The authoring context, with the guided-facilitation layer added when chosen."""
        context = self._workflows.compile(CompileMode.AUTHORING, META, job=job)
        if not guided:
            return context
        guide = self._workflows.meta_guide()
        return f"{context}\n\n\n{guide}" if guide else context
