# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ExportUsage use case: assemble a job's usage report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.tool_calls import ToolCalls
from generic_ml_wrapper.application.domain.model.turn_origin import TurnRole
from generic_ml_wrapper.application.port.inbound.export_usage import (
    AgentTotal,
    ExportUsage,
    ModelTotal,
    SessionTotal,
    ToolTotal,
    TurnRow,
    UsageReport,
)
from generic_ml_wrapper.application.port.outbound.incident_log import IncidentLogPort
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage

# The ``cache_*_tokens`` fields carry ``# nosemgrep``: they count a model's tokens, not
# secrets, and the scanner's hard-coded-token rule matches on the name alone.
_UNKNOWN_MODEL = "(unknown)"


class ExportUsageUseCase(ExportUsage):
    """Assemble a job's usage report from the per-turn store and the session-cost store."""

    def __init__(
        self, usage: UsageStorePort, turns: PerTurnMeteringPort, incidents: IncidentLogPort
    ) -> None:
        """Wire the use case to its usage stores.

        Args:
            usage: The per-session cost store (from the status line).
            turns: The per-turn token store (from a metering gateway).
            incidents: The connection incidents the gateway recorded.
        """
        self._usage = usage
        self._turns = turns
        self._incidents = incidents

    def execute(self, job: str, sessions: Sequence[str] = ()) -> UsageReport:
        """Build a job's usage report.

        Args:
            job: The job identifier.
            sessions: Narrow the report to these sessions; empty for all of them.

        Returns:
            Per-turn rows (chronological), totals by model, agent, session and tool, and
            the job's totals.
        """
        wanted = set(sessions)

        def kept(session: str) -> bool:
            return not wanted or session in wanted

        recorded = [turn for turn in self._turns.turns_for_job(job) if kept(turn.session_id)]
        costs = {
            session: cost
            for session, cost in self._usage.session_costs(job).items()
            if kept(session)
        }
        whole = _Sum.of(recorded)
        return UsageReport(
            job=job,
            sessions_filter=tuple(sessions),
            turns=tuple(sorted((_row(turn) for turn in recorded), key=lambda row: row.timestamp)),
            models=_model_totals(recorded),
            agents=_agent_totals(recorded),
            sessions=_session_totals(recorded, costs),
            tools=tuple(
                ToolTotal(tool, calls)
                for tool, calls in ToolCalls.summed(turn.tool_calls for turn in recorded).counts
            ),
            turn_count=whole.calls,
            input_tokens=whole.input_tokens,
            output_tokens=whole.output_tokens,
            cache_read_tokens=whole.cache_read_tokens,
            cache_write_tokens=whole.cache_write_tokens,
            duration_s=whole.duration_s,
            total_usd=round(sum(costs.values()), 2),
            incidents=tuple(
                incident
                for incident in self._incidents.incidents(job=job)
                if kept(incident.session_id)
            ),
        )


@dataclass(frozen=True)
class _Sum:
    """The counts every grouping of turns adds up."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0  # nosemgrep
    cache_write_tokens: int = 0  # nosemgrep
    duration_s: float = 0.0

    @classmethod
    def of(cls, turns: Iterable[TurnUsage]) -> _Sum:
        listed = list(turns)
        return cls(
            len(listed),
            sum(turn.input_tokens for turn in listed),
            sum(turn.output_tokens for turn in listed),
            sum(turn.cache_read_tokens for turn in listed),
            sum(turn.cache_creation_tokens for turn in listed),
            round(sum(turn.duration_s for turn in listed), 1),
        )


def _row(turn: TurnUsage) -> TurnRow:
    return TurnRow(
        timestamp=turn.timestamp,
        model=turn.model or _UNKNOWN_MODEL,
        duration_s=turn.duration_s,
        input_tokens=turn.input_tokens,
        output_tokens=turn.output_tokens,
        cache_read_tokens=turn.cache_read_tokens,
        cache_write_tokens=turn.cache_creation_tokens,
        session_id=turn.session_id,
        turn_id=turn.turn_id,
        role=turn.role,
        agent=turn.agent,
        caused_by_agent=turn.caused_by_agent,
        tool_calls=turn.tool_calls.as_dict(),
    )


def _model_totals(recorded: list[TurnUsage]) -> tuple[ModelTotal, ...]:
    by_model: dict[str, list[TurnUsage]] = {}
    for turn in recorded:
        by_model.setdefault(turn.model or _UNKNOWN_MODEL, []).append(turn)
    return tuple(
        ModelTotal(model, *_fields(_Sum.of(turns))) for model, turns in sorted(by_model.items())
    )


def _agent_totals(recorded: list[TurnUsage]) -> tuple[AgentTotal, ...]:
    if all(turn.role is TurnRole.MAIN and not turn.caused_by_agent for turn in recorded):
        return ()
    by_side: dict[tuple[TurnRole, str | None, bool], list[TurnUsage]] = {}
    for turn in recorded:
        by_side.setdefault((turn.role, turn.agent, turn.caused_by_agent), []).append(turn)
    # The main conversation first -- its turns the agents caused right after its others --
    # then the agents: unnamed before named, by name.
    order = sorted(by_side, key=lambda key: (key[0] is TurnRole.AGENT, key[1] or "", key[2]))
    return tuple(
        AgentTotal(role, agent, *_fields(_Sum.of(by_side[role, agent, caused])), caused)
        for role, agent, caused in order
    )


def _session_totals(recorded: list[TurnUsage], costs: dict[str, float]) -> tuple[SessionTotal, ...]:
    """Every session with a metered turn or a recorded cost, by session id."""
    by_session: dict[str, list[TurnUsage]] = {session: [] for session in costs}
    for turn in recorded:
        by_session.setdefault(turn.session_id, []).append(turn)
    return tuple(
        SessionTotal(session, *_fields(_Sum.of(turns)), costs.get(session))
        for session, turns in sorted(by_session.items())
    )


def _fields(total: _Sum) -> tuple[int, int, int, int, int, float]:
    """A sum's counts in the order every total's fields take them."""
    return (
        total.calls,
        total.input_tokens,
        total.output_tokens,
        total.cache_read_tokens,
        total.cache_write_tokens,
        total.duration_s,
    )
