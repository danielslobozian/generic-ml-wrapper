# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for reporting a job's recorded usage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TurnRow:
    """One metered turn, for the per-turn table.

    Attributes:
        timestamp: The turn's wall-clock time (epoch seconds), or ``0.0``.
        model: The model that served the turn.
        duration_s: How long the turn took, in seconds.
        input_tokens: Fresh prompt tokens.
        output_tokens: Completion tokens.
        cache_tokens: Cache creation + read prompt tokens.
        turn_id: The provider's id for the turn, or ``None``.
    """

    timestamp: float
    model: str
    duration_s: float
    input_tokens: int
    output_tokens: int
    cache_tokens: int
    turn_id: str | None


@dataclass(frozen=True)
class ModelTotal:
    """A model's totals across the job.

    Attributes:
        model: The model's name.
        calls: How many turns this model served.
        input_tokens: Total fresh prompt tokens.
        output_tokens: Total completion tokens.
        cache_tokens: Total cache prompt tokens.
        duration_s: Total duration, in seconds.
    """

    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_tokens: int
    duration_s: float


@dataclass(frozen=True)
class SessionCost:
    """A session's recorded cost.

    Attributes:
        session_id: The session's human-readable id.
        cost_usd: The session's cumulative cost in USD.
    """

    session_id: str
    cost_usd: float


@dataclass(frozen=True)
class UsageReport:
    """A job's recorded usage: per-turn rows, totals by model, cost by session, totals.

    Attributes:
        job: The job identifier.
        turns: Every metered turn, chronological.
        models: Totals by model, sorted by model name.
        session_costs: Recorded cost per session, sorted by session id.
        turn_count: The number of metered turns.
        input_tokens: The job's total fresh prompt tokens.
        output_tokens: The job's total completion tokens.
        cache_tokens: The job's total cache prompt tokens.
        duration_s: The job's total metered duration, in seconds.
        total_usd: The job's total cost across its sessions.
    """

    job: str
    turns: tuple[TurnRow, ...] = ()
    models: tuple[ModelTotal, ...] = ()
    session_costs: tuple[SessionCost, ...] = ()
    turn_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_tokens: int = 0
    duration_s: float = 0.0
    total_usd: float = 0.0


class ExportUsage(ABC):
    """Report the usage recorded for a job."""

    @abstractmethod
    def execute(self, job: str) -> UsageReport:
        """Build a job's usage report.

        Args:
            job: The job identifier.

        Returns:
            The job's per-turn rows, per-model totals, per-session cost, and totals.
        """
