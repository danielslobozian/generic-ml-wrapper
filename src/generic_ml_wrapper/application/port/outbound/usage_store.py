# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for persisting metered usage."""

from __future__ import annotations

from abc import ABC, abstractmethod


class UsageStorePort(ABC):
    """Persist and read per-session usage recorded from a client's status payload."""

    @abstractmethod
    def record_session_cost(self, job: str, session: str, cost_usd: float) -> None:
        """Record a session's cumulative cost (monotonic: the highest seen wins).

        Args:
            job: The job the session belongs to.
            session: The session id.
            cost_usd: The session's cumulative cost in USD.
        """

    @abstractmethod
    def session_costs(self, job: str) -> dict[str, float]:
        """Return the recorded cost per session for a job.

        Args:
            job: The job identifier.

        Returns:
            A mapping of session id to cumulative cost (empty if none recorded).
        """
