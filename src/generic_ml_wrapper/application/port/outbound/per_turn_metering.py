# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for recording per-turn usage a gateway meters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage


class PerTurnMeteringPort(ABC):
    """Persist and read the per-turn token usage a metering gateway observes.

    This is the deep-metering counterpart to the session-level cost store: where the
    status line records one cumulative cost per session, a gateway records one entry
    per request/response round.
    """

    @abstractmethod
    def record(self, job: str, turn: TurnUsage) -> None:
        """Append one metered turn for a job.

        Args:
            job: The job the turn belongs to.
            turn: The turn's usage.
        """

    @abstractmethod
    def turns_for_job(self, job: str) -> list[TurnUsage]:
        """Return every recorded turn for a job, in the order recorded.

        Args:
            job: The job identifier.

        Returns:
            The recorded turns (empty if none).
        """
