# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A job's recorded usage: per-turn rows, totals by model, cost by session, totals."""

from __future__ import annotations

from dataclasses import dataclass

from generic_ml_wrapper.application.domain.model.session_cost import SessionCost
from generic_ml_wrapper.application.port.inbound.model_total import ModelTotal
from generic_ml_wrapper.application.port.inbound.turn_row import TurnRow


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
