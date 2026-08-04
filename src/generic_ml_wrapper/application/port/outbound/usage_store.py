# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for persisting metered usage."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.domain.model.session_cost import SessionCost


class UsageStorePort(ABC):
    """Persist and read per-session usage recorded from a client's status payload."""

    @abstractmethod
    def record_session_cost(self, job: str, cost: SessionCost) -> None:
        """Record a session's cumulative cost (monotonic: the highest seen wins).

        Takes a :class:`SessionCost` rather than a session id and a bare number, so a
        caller cannot reach the store with an amount nothing has checked. The turn store
        has always worked this way; this is the same guarantee on the shallower
        measurement.

        The session must already be recorded, for the same reason a metered turn's must:
        an implementation may refuse a cost for a session it does not know.

        Args:
            job: The job the session belongs to.
            cost: The session's cumulative cost.
        """

    @abstractmethod
    def session_costs(self, job: str) -> dict[str, float]:
        """Return the recorded cost per session for a job.

        Args:
            job: The job identifier.

        Returns:
            A mapping of session id to cumulative cost (empty if none recorded).
        """
