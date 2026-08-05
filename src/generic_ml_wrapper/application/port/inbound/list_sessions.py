# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing a job's sessions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionSummary:
    """A one-line summary of a recorded session.

    Attributes:
        session_id: The session's human-readable id.
        client: The client the session runs on.
        cwd: The folder it was launched in, or ``None`` for a pre-folder session.
        resumable: Whether this session can be resumed (its client supports it).
        created_at: When it was first recorded (ISO string), or ``None``.
        turn_count: How many metered turns it recorded. ``0`` marks a session that never
            got going -- one started and abandoned at the prompt is recorded like any
            other, and this is what distinguishes it.
        cost_usd: Its recorded cumulative cost, or ``0.0`` if none was ever metered.
    """

    session_id: str
    client: str
    cwd: str | None = None
    resumable: bool = True
    created_at: str | None = None
    turn_count: int = 0
    cost_usd: float = 0.0


class ListSessionsUseCase(ABC):
    """List the sessions recorded for a job."""

    @abstractmethod
    def execute(self, job: str) -> list[SessionSummary]:
        """List a job's sessions.

        Args:
            job: The job identifier.

        Returns:
            One summary per session, oldest first.
        """
