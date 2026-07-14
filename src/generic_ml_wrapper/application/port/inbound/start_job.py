# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for starting work on a job."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class StartJobCommand:
    """A request to start (or resume) a session on a job.

    Attributes:
        job: The job identifier.
        client: The client to launch.
        resume_latest: Resume the job's most recent session instead of minting one.
        workflow: A workflow to run on the job, or ``None`` for the plain wrapper.
    """

    job: str
    client: str
    resume_latest: bool = False
    workflow: str | None = None


class UnknownWorkflowError(ValueError):
    """Raised when a requested workflow does not exist."""


class ResumeNotSupportedError(ValueError):
    """Raised when resuming is requested for a client that cannot resume (e.g. codex)."""


class StartJob(ABC):
    """Start or resume a session on a job and hand over to the client."""

    @abstractmethod
    def execute(self, command: StartJobCommand) -> int:
        """Run the use case.

        Args:
            command: The request describing job, client, resume, and workflow.

        Returns:
            The client's exit code.

        Raises:
            UnknownWorkflowError: If a workflow was requested but does not exist.
            ResumeNotSupportedError: If resume was requested for a client whose
                caller cannot resume a session.
        """
