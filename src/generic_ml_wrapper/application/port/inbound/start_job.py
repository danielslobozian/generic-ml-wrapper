# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for starting work on a job."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.start_job_command import StartJobCommand
from generic_ml_wrapper.application.port.inbound.start_job_result import StartJobResult


class StartJobUseCase(ABC):
    """Start or resume a session on a job and hand over to the client."""

    @abstractmethod
    def execute(self, command: StartJobCommand) -> StartJobResult:
        """Run the use case.

        Args:
            command: The request describing job, client, resume, and workflow.

        Returns:
            The run's outcome: exit code, job, and the session that ran.

        Raises:
            UnknownWorkflowError: If a workflow was requested but does not exist.
            ResumeNotSupportedError: If resume was requested for a client whose
                caller cannot resume a session.
        """
