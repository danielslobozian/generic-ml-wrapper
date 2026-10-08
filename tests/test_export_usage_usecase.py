# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ExportUsage use case, driven by fake usage stores."""

from _conformance import InMemoryIncidentLog, an_incident

from generic_ml_wrapper.application.domain.model.turn_origin import TurnRole
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.port.inbound.export_usage import (
    AgentTotal,
    ModelTotal,
    SessionCost,
    UsageReport,
)
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort
from generic_ml_wrapper.application.usecase.export_usage import ExportUsageUseCase


class FakeUsageStore(UsageStorePort):
    def __init__(self, costs: dict[str, float]) -> None:
        self._costs = costs

    def record_session_cost(self, job: str, session: str, cost_usd: float) -> None:
        raise NotImplementedError

    def session_costs(self, job: str) -> dict[str, float]:
        return self._costs


class FakeTurnStore(PerTurnMeteringPort):
    def __init__(self, turns: list[TurnUsage] | None = None) -> None:
        self._turns = turns or []

    def record(self, job: str, turn: TurnUsage) -> None:
        raise NotImplementedError

    def turns_for_job(self, job: str) -> list[TurnUsage]:
        return self._turns


def test_empty_report() -> None:
    report = ExportUsageUseCase(FakeUsageStore({}), FakeTurnStore(), InMemoryIncidentLog()).execute(
        "JOB-1"
    )
    assert report.job == "JOB-1"
    assert report.turns == ()
    assert report.models == ()
    assert report.session_costs == ()
    assert report.turn_count == 0
    assert report.total_usd == 0.0


def test_costs_become_sorted_session_cost_rows() -> None:
    store = FakeUsageStore({"JOB-1_002": 0.09, "JOB-1_001": 0.43})
    report = ExportUsageUseCase(store, FakeTurnStore(), InMemoryIncidentLog()).execute("JOB-1")
    assert report.session_costs == (SessionCost("JOB-1_001", 0.43), SessionCost("JOB-1_002", 0.09))
    assert report.total_usd == 0.52


def test_turns_are_chronological_with_totals_by_model() -> None:
    turns = FakeTurnStore(
        [
            TurnUsage(
                "JOB-1_001", 100, 20, None, "gpt-b", timestamp=200.0, duration_s=1.0, turn_id="t2"
            ),
            TurnUsage(
                "JOB-1_001",
                50,
                30,
                None,
                "gpt-a",
                cache_read_tokens=5,
                timestamp=100.0,
                duration_s=2.0,
                turn_id="t1",
            ),
            TurnUsage(
                "JOB-1_001", 10, 5, None, "gpt-a", timestamp=300.0, duration_s=0.5, turn_id="t3"
            ),
        ]
    )
    report = ExportUsageUseCase(
        FakeUsageStore({"JOB-1_001": 0.5}), turns, InMemoryIncidentLog()
    ).execute("JOB-1")

    assert [turn.turn_id for turn in report.turns] == ["t1", "t2", "t3"]  # chronological
    assert report.models == (
        ModelTotal(
            "gpt-a", calls=2, input_tokens=60, output_tokens=35, cache_tokens=5, duration_s=2.5
        ),
        ModelTotal(
            "gpt-b", calls=1, input_tokens=100, output_tokens=20, cache_tokens=0, duration_s=1.0
        ),
    )
    assert report.turn_count == 3
    assert report.input_tokens == 160
    assert report.output_tokens == 55
    assert report.cache_tokens == 5
    assert report.duration_s == 3.5
    assert report.total_usd == 0.5


def test_the_jobs_incidents_are_in_the_report() -> None:
    mine = an_incident(job="JOB-1", at=2.0)
    log = InMemoryIncidentLog([an_incident(job="JOB-2"), mine])
    report = ExportUsageUseCase(FakeUsageStore({}), FakeTurnStore(), log).execute("JOB-1")
    assert report.incidents == (mine,)


def _export(turns: list[TurnUsage]) -> UsageReport:
    return ExportUsageUseCase(
        FakeUsageStore({}), FakeTurnStore(turns), InMemoryIncidentLog()
    ).execute("JOB-1")


def test_a_job_with_only_main_turns_has_no_agent_totals() -> None:
    assert _export([TurnUsage("JOB-1_001", 1, 2, None, "m")]).agents == ()


def test_agent_totals_put_main_first_then_unnamed_then_named_agents() -> None:
    agent = TurnRole.AGENT
    report = _export(
        [
            TurnUsage("S", 10, 1, None, "m", duration_s=1.0, role=agent, agent="zeta"),
            TurnUsage("S", 20, 2, None, "m", cache_read_tokens=7, duration_s=2.0),
            TurnUsage("S", 30, 3, None, "m", duration_s=0.5, role=agent),
            TurnUsage("S", 40, 4, None, "m", duration_s=0.5, role=agent, agent="alpha"),
            TurnUsage("S", 50, 5, None, "m", duration_s=1.5, role=agent, agent="zeta"),
        ]
    )
    assert report.agents == (
        AgentTotal(TurnRole.MAIN, None, 1, 20, 2, 7, 2.0),
        AgentTotal(agent, None, 1, 30, 3, 0, 0.5),
        AgentTotal(agent, "alpha", 1, 40, 4, 0, 0.5),
        AgentTotal(agent, "zeta", 2, 60, 6, 0, 2.5),
    )
    assert [(row.role, row.agent) for row in report.turns][:2] == [
        (agent, "zeta"),
        (TurnRole.MAIN, None),
    ]
