# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for reopening a recorded session."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.resume_session_command import ResumeSessionCommand
from generic_ml_wrapper.application.port.inbound.start_job_result import StartJobResult


class ResumeSessionForJobUseCase(ABC):
    """Reopen a recorded session on the client that made it."""

    @abstractmethod
    def execute(self, command: ResumeSessionCommand) -> StartJobResult:
        """Reopen the session.

        Nothing is recorded and no context is recomposed: the client still holds the
        conversation, and the session already exists.

        Args:
            command: The session to reopen.

        Returns:
            The run's outcome: exit code, job, and the session that ran.

        Raises:
            ResumeNotSupportedError: When the session's client cannot reopen it — either
                the client has no resume at all, or the session's client-side id was
                never learned.
        """
