# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for removing recorded sessions from a job."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from generic_ml_wrapper.common.errors import DomainError


@dataclass(frozen=True)
class SessionFootprint:
    """Everything one session holds -- what a delete would take with it.

    Shown before a delete is confirmed, and returned after one, so "what will go" and
    "what went" are the same shape rather than two descriptions that can disagree.

    Attributes:
        job: The job the session belongs to.
        session: The session's ``<job>_NNN`` id.
        turns: Metered turns recorded for it (``0`` for a session abandoned before its
            first turn -- the case a delete most often exists for).
        cost_usd: Its recorded cumulative cost.
        contexts: Compiled-context files it holds (0 or 1).
        transcript_calls: Transcript files it holds (``0`` unless transcripts were on).
    """

    job: str
    session: str
    turns: int
    cost_usd: float
    contexts: int
    transcript_calls: int


class NoSuchJobError(DomainError, ValueError):
    """Raised when the named job has no recorded activity."""


class NoSuchSessionError(DomainError, ValueError):
    """Raised when the named session is not recorded for its job."""


class DeleteSessions(ABC):
    """Remove recorded sessions from a job, with their usage and their files."""

    @abstractmethod
    def preview(self, job: str, sessions: Sequence[str]) -> list[SessionFootprint]:
        """Report what deleting these sessions would remove, without removing it.

        Args:
            job: The job the sessions belong to.
            sessions: The session ids to measure, in the order given.

        Returns:
            One footprint per session, in the order given.

        Raises:
            NoSuchJobError: If the job has no recorded activity.
            NoSuchSessionError: If any session is not recorded for the job.
        """

    @abstractmethod
    def execute(self, job: str, sessions: Sequence[str]) -> list[SessionFootprint]:
        """Delete the sessions, their recorded usage, and their files.

        The whole batch is validated before anything is removed: one unknown id leaves
        every other session untouched, rather than deleting half the request and then
        failing on the rest.

        Args:
            job: The job the sessions belong to.
            sessions: The session ids to delete, in the order given.

        Returns:
            One footprint per deleted session -- what was actually removed.

        Raises:
            NoSuchJobError: If the job has no recorded activity.
            NoSuchSessionError: If any session is not recorded for the job.
        """
