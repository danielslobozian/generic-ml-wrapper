# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for starting a fresh session on a job."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.start_job_result import StartJobResult
from generic_ml_wrapper.application.port.inbound.start_new_session_command import (
    StartNewSessionCommand,
)


class StartNewSessionForJobUseCase(ABC):
    """Start a fresh session on an existing job and run the client on it."""

    @abstractmethod
    def execute(self, command: StartNewSessionCommand) -> StartJobResult:
        """Mint a session, record it, and run the client.

        Args:
            command: The job, the client, and what to run on it.

        Returns:
            The run's outcome: exit code, job, and the session that ran.

        Raises:
            NoSuchJobError: When the job does not exist. Create it first.
            UnknownWorkflowError: When a workflow was named but is not installed.
        """
