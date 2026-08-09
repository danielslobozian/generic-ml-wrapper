# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ResumeSessionForJobUseCase use case: reopen a session on the client that made it."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.resume_not_supported_error import (
    ResumeNotSupportedError,
)
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.port.inbound.resume_session_command import ResumeSessionCommand
from generic_ml_wrapper.application.port.inbound.resume_session_for_job import (
    ResumeSessionForJobUseCase,
)
from generic_ml_wrapper.application.port.inbound.start_job_result import StartJobResult
from generic_ml_wrapper.application.port.outbound.cli_caller_provider import CliCallerProviderPort
from generic_ml_wrapper.application.usecase.client_arguments_binder import ClientArgumentsBinder
from generic_ml_wrapper.application.usecase.launch import LaunchSequence


class ResumeSessionForJobService(ResumeSessionForJobUseCase):
    """Reopen a recorded session on the client that made it."""

    def __init__(
        self,
        callers: CliCallerProviderPort,
        launch: LaunchSequence,
        client_arguments: ClientArgumentsBinder,
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            callers: Resolves the caller for the session's own client.
            launch: The bracketed launch sequence (hooks, metering, the client).
            client_arguments: Attaches the passthrough launch arguments.
        """
        self._callers = callers
        self._launch = launch
        self._client_arguments = client_arguments

    def execute(self, command: ResumeSessionCommand) -> StartJobResult:
        """Reopen the session.

        Args:
            command: The session to reopen.

        Returns:
            The run's outcome: exit code, job, and the session that ran.

        Raises:
            ResumeNotSupportedError: When the session's client cannot reopen it.
        """
        run = self._client_arguments.bind(self._run_for(command.session), command.client_args)
        caller = self._callers.for_run(run)
        if not caller.can_resume():
            self._refuse(run)
        exit_code = self._launch.run(caller, run)
        return StartJobResult(exit_code=exit_code, job=run.job, session_id=run.session_id)

    @staticmethod
    def _run_for(session: Session) -> RunContext:
        """Build the run that reopens a session -- in the folder it was launched in.

        Args:
            session: The session being reopened.

        Returns:
            A resuming run. ``cwd`` is the session's stored folder (``None`` for
            pre-folder sessions, which resume in the current directory as before);
            Claude's resume is scoped to that folder.
        """
        return RunContext(
            job=session.job,
            session_id=session.session_id,
            client=session.client,
            uuid=session.uuid,
            resume=True,
            cwd=session.cwd,
        )

    @staticmethod
    def _refuse(run: RunContext) -> None:
        """Refuse a resume the caller cannot perform.

        Args:
            run: The run that was about to be reopened.

        Raises:
            ResumeNotSupportedError: Always. Two different refusals wear this one error:
                some clients cannot resume at all; others (codex) can, but only a session
                whose client-side id was learned — one that died before its first turn has
                none. Say which, because the fixes are not the same.
        """
        if run.uuid is None:
            raise ResumeNotSupportedError("error.workflow.resume_unsupported", client=run.client)
        raise ResumeNotSupportedError(
            "error.workflow.resume_lost", session_id=run.session_id, client=run.client
        )
