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
        attachment: What it was started with, as ``name@version`` (just the name for a
            session recorded before attachments), or ``None`` for a plain session.
        incidents: How many connection incidents it suffered (lost connections and
            cut-off answers).
    """

    session_id: str
    client: str
    cwd: str | None = None
    resumable: bool = True
    created_at: str | None = None
    turn_count: int = 0
    cost_usd: float = 0.0
    attachment: str | None = None
    incidents: int = 0


class ListSessions(ABC):
    """List the sessions recorded for a job."""

    @abstractmethod
    def execute(self, job: str) -> list[SessionSummary]:
        """List a job's sessions.

        Args:
            job: The job identifier.

        Returns:
            One summary per session, oldest first.
        """
