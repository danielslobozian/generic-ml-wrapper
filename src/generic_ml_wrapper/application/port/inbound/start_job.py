# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for starting work on a job."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from generic_ml_wrapper.common.errors import DomainError


@dataclass(frozen=True)
class StartJobCommand:
    """A request to start (or resume) a session on a job.

    Attributes:
        job: The job identifier.
        client: The client to launch.
        resume_latest: Resume the job's most recent session instead of minting one.
        resume_session: Resume this specific session id instead of the latest; takes
            precedence over ``resume_latest``. ``None`` means "not a specific-session resume".
        attachment: An attachment to run the new session with, or ``None``.
        attachment_version: The attachment's version (``MAJOR.MINOR.PATCH``), or ``None``
            for the highest stored.
        note: An extra paragraph for a new session's opening message, or ``None``.
        client_args: Passthrough launch arguments for this call, replacing whatever
            is configured for the client; ``None`` means "use the configured value".
        tags: Tags to put on the job once its session is recorded (kept with any it
            already has), e.g. the sprint it belongs to.
    """

    job: str
    client: str
    resume_latest: bool = False
    resume_session: str | None = None
    attachment: str | None = None
    attachment_version: str | None = None
    note: str | None = None
    client_args: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class StartJobResult:
    """The outcome of a run, carrying what the exit receipt needs.

    Attributes:
        exit_code: The client's exit code.
        job: The job the session ran on.
        session_id: The session that ran (new or resumed).
    """

    exit_code: int
    job: str
    session_id: str


class ResumeNotSupportedError(DomainError, ValueError):
    """Raised when resuming is requested for a client that cannot resume (e.g. codex)."""


class StartJob(ABC):
    """Start or resume a session on a job and hand over to the client."""

    @abstractmethod
    def execute(self, command: StartJobCommand) -> StartJobResult:
        """Run the use case.

        Args:
            command: The request describing job, client, resume, and attachment.

        Returns:
            The run's outcome: exit code, job, and the session that ran.

        Raises:
            AttachmentError: If the attachment, or that version, is not stored, or has
                changed since its import.
            ResumeNotSupportedError: If resume was requested for a client whose
                caller cannot resume a session.
        """
