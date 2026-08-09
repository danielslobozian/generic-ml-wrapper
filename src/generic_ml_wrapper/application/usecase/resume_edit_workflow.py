# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ResumeEditWorkflowUseCase use case: pick up an interrupted edit where it stopped."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.authoring_job import AuthoringJob
from generic_ml_wrapper.application.domain.model.no_edit_to_resume_error import NoEditToResumeError
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.port.inbound.resume_edit_workflow import (
    ResumeEditWorkflowUseCase,
)
from generic_ml_wrapper.application.port.inbound.resume_edit_workflow_command import (
    ResumeEditWorkflowCommand,
)
from generic_ml_wrapper.application.port.outbound.cli_caller_provider import CliCallerProviderPort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.launch import LaunchSequence
from generic_ml_wrapper.application.usecase.workflow_folder import folder_for_editing


class ResumeEditWorkflowService(ResumeEditWorkflowUseCase):
    """Reopen the most recent editing session of a workflow, in its own folder."""

    def __init__(
        self,
        workflows: WorkflowSourcePort,
        store: SessionStorePort,
        callers: CliCallerProviderPort,
        launch: LaunchSequence,
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            workflows: Locates the workflow's folder.
            store: Where the authoring sessions are read from.
            callers: Resolves the caller for the session's own client.
            launch: The bracketed launch sequence (hooks, metering, the client).
        """
        self._workflows = workflows
        self._store = store
        self._callers = callers
        self._launch = launch

    def execute(self, command: ResumeEditWorkflowCommand) -> int:
        """Reopen the edit.

        Nothing is recorded and no context is re-injected: the client still holds the
        edit conversation, and re-sending it would talk over that history.

        Args:
            command: Names the workflow to pick up.

        Returns:
            The client's exit code.

        Raises:
            NoEditToResumeError: When the workflow has no editing session, or that
                session's client cannot reopen one.
        """
        name = command.workflow_name
        folder = folder_for_editing(self._workflows, name)
        run = self._run_for(name, folder)
        caller = self._callers.for_run(run)
        if not caller.can_resume():
            raise NoEditToResumeError(
                "error.workflow.no_edit_resume_unsupported",
                client=run.client,
                session_id=run.session_id,
            )
        return self._launch.run(caller, run)

    def _run_for(self, name: str, folder: str) -> RunContext:
        """Build the run that reopens this workflow's last edit.

        Only sessions that ran *in the workflow's folder* count. Every edit of every
        workflow files under the one authoring job, so the job's latest session is just
        as likely to be an edit of something else — and reopening one of those would
        relaunch it in the wrong directory, where a cwd-scoped client correctly reports
        no such conversation. That also excludes edits recorded before the folder was
        stored: their folder is unknown, so guessing would reopen the wrong conversation
        rather than none.

        Args:
            name: The workflow being picked up.
            folder: Its folder.

        Returns:
            A resuming run pointed at that folder.

        Raises:
            NoEditToResumeError: When no session ran in this folder.
        """
        job = AuthoringJob.NAME
        edits = [s for s in self._store.sessions_for_job(job) if s.cwd == folder]
        if not edits:
            raise NoEditToResumeError("error.workflow.no_edit_session", name=name)
        session = edits[-1]
        return RunContext(
            job=job,
            session_id=session.session_id,
            client=session.client,
            uuid=session.uuid,
            resume=True,
            cwd=folder,
            kickoff=(
                f"You are picking up an interrupted edit of the workflow {name!r}. Your "
                f"working directory is its folder ({folder}). Take stock of what you had "
                "already changed, tell me, then carry on from there — do not start over."
            ),
        )
