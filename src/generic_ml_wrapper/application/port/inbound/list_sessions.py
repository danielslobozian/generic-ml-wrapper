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
    """

    session_id: str
    client: str


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
