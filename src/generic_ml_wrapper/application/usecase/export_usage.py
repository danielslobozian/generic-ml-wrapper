# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ExportUsage use case: assemble a job's usage report."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.export_usage import (
    ExportUsage,
    ModelTotal,
    SessionCost,
    TurnRow,
    UsageReport,
)
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage

_UNKNOWN_MODEL = "(unknown)"


class ExportUsageUseCase(ExportUsage):
    """Assemble a job's usage report from the per-turn store and the session-cost store."""

    def __init__(self, usage: UsageStorePort, turns: PerTurnMeteringPort) -> None:
        """Wire the use case to its usage stores.

        Args:
            usage: The per-session cost store (from the status line).
            turns: The per-turn token store (from a metering gateway).
        """
        self._usage = usage
        self._turns = turns

    def execute(self, job: str) -> UsageReport:
        """Build a job's usage report.

        Args:
            job: The job identifier.

        Returns:
            Per-turn rows (chronological), per-model totals, per-session cost, and
            job totals.
        """
        recorded = self._turns.turns_for_job(job)
        turns = tuple(sorted((_row(turn) for turn in recorded), key=lambda row: row.timestamp))
        models = _model_totals(recorded)
        costs = self._usage.session_costs(job)
        session_costs = tuple(SessionCost(session, costs[session]) for session in sorted(costs))
        return UsageReport(
            job=job,
            turns=turns,
            models=models,
            session_costs=session_costs,
            turn_count=len(recorded),
            input_tokens=sum(model.input_tokens for model in models),
            output_tokens=sum(model.output_tokens for model in models),
            cache_tokens=sum(model.cache_tokens for model in models),
            duration_s=round(sum(model.duration_s for model in models), 1),
            total_usd=round(sum(cost.cost_usd for cost in session_costs), 2),
        )


def _row(turn: TurnUsage) -> TurnRow:
    return TurnRow(
        timestamp=turn.timestamp,
        model=turn.model or _UNKNOWN_MODEL,
        duration_s=turn.duration_s,
        input_tokens=turn.input_tokens,
        output_tokens=turn.output_tokens,
        cache_tokens=turn.cache_creation_tokens + turn.cache_read_tokens,
        turn_id=turn.turn_id,
    )


def _model_totals(recorded: list[TurnUsage]) -> tuple[ModelTotal, ...]:
    # model -> [calls, input, output, cache, duration]
    totals: dict[str, list[float]] = {}
    for turn in recorded:
        model = turn.model or _UNKNOWN_MODEL
        acc = totals.setdefault(model, [0, 0, 0, 0, 0.0])
        acc[0] += 1
        acc[1] += turn.input_tokens
        acc[2] += turn.output_tokens
        acc[3] += turn.cache_creation_tokens + turn.cache_read_tokens
        acc[4] += turn.duration_s
    return tuple(
        ModelTotal(model, int(a[0]), int(a[1]), int(a[2]), int(a[3]), round(a[4], 1))
        for model, a in sorted(totals.items())
    )
