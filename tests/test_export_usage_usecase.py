# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ExportUsage use case, driven by fake usage stores."""

from _conformance import InMemoryIncidentLog, an_incident

from generic_ml_wrapper.application.domain.model.execution_tags import ExecutionTags
from generic_ml_wrapper.application.domain.model.tool_calls import ToolCalls
from generic_ml_wrapper.application.domain.model.turn_origin import TurnRole
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.port.inbound.export_usage import (
    AgentTotal,
    ModelTotal,
    SessionTotal,
    TagTotal,
    ToolTotal,
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
    assert report.sessions == ()
    assert report.turn_count == 0
    assert report.total_usd == 0.0


def test_costs_become_sorted_session_rows() -> None:
    store = FakeUsageStore({"JOB-1_002": 0.09, "JOB-1_001": 0.43})
    report = ExportUsageUseCase(store, FakeTurnStore(), InMemoryIncidentLog()).execute("JOB-1")
    assert report.sessions == (
        SessionTotal("JOB-1_001", 0, 0, 0, 0, 0, 0.0, 0.43),
        SessionTotal("JOB-1_002", 0, 0, 0, 0, 0, 0.0, 0.09),
    )
    assert report.total_usd == 0.52


def test_a_session_totals_its_turns_and_carries_its_cost_when_reported() -> None:
    turns = FakeTurnStore(
        [
            TurnUsage("S1", 10, 2, None, "m", cache_read_tokens=100, duration_s=1.0),
            TurnUsage("S1", 20, 3, None, "m", cache_creation_tokens=7, duration_s=2.0),
            TurnUsage("S2", 5, 1, None, "m", duration_s=0.5),
        ]
    )
    report = ExportUsageUseCase(FakeUsageStore({"S1": 0.25}), turns, InMemoryIncidentLog()).execute(
        "JOB-1"
    )
    assert report.sessions == (
        SessionTotal("S1", 2, 30, 5, 100, 7, 3.0, 0.25),
        SessionTotal("S2", 1, 5, 1, 0, 0, 0.5, None),
    )


def test_the_report_narrows_to_the_sessions_asked_for() -> None:
    turns = FakeTurnStore([TurnUsage("S1", 10, 1, None, "m"), TurnUsage("S2", 20, 2, None, "m")])
    log = InMemoryIncidentLog([an_incident(session="S1"), an_incident(session="S2", at=2.0)])
    report = ExportUsageUseCase(FakeUsageStore({"S1": 0.1, "S2": 0.2}), turns, log).execute(
        "JOB-1", ["S2"]
    )
    assert report.sessions_filter == ("S2",)
    assert [turn.session_id for turn in report.turns] == ["S2"]
    assert report.input_tokens == 20
    assert report.total_usd == 0.2
    assert [incident.session_id for incident in report.incidents] == ["S2"]


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
        ModelTotal("gpt-a", 2, 60, 35, cache_read_tokens=5, cache_write_tokens=0, duration_s=2.5),
        ModelTotal("gpt-b", 1, 100, 20, cache_read_tokens=0, cache_write_tokens=0, duration_s=1.0),
    )
    assert report.turn_count == 3
    assert report.input_tokens == 160
    assert report.output_tokens == 55
    assert report.cache_read_tokens == 5
    assert report.cache_write_tokens == 0
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
        AgentTotal(TurnRole.MAIN, None, 1, 20, 2, 7, 0, 2.0),
        AgentTotal(agent, None, 1, 30, 3, 0, 0, 0.5),
        AgentTotal(agent, "alpha", 1, 40, 4, 0, 0, 0.5),
        AgentTotal(agent, "zeta", 2, 60, 6, 0, 0, 2.5),
    )
    assert [(row.role, row.agent) for row in report.turns][:2] == [
        (agent, "zeta"),
        (TurnRole.MAIN, None),
    ]


def test_the_main_turns_the_agents_caused_are_totalled_apart() -> None:
    report = _export(
        [
            TurnUsage("S", 20, 2, None, "m", duration_s=2.0),
            TurnUsage("S", 30, 3, None, "m", duration_s=1.0, caused_by_agent=True),
        ]
    )
    assert report.agents == (
        AgentTotal(TurnRole.MAIN, None, 1, 20, 2, 0, 0, 2.0),
        AgentTotal(TurnRole.MAIN, None, 1, 30, 3, 0, 0, 1.0, caused_by_agent=True),
    )
    assert [row.caused_by_agent for row in report.turns] == [False, True]


def test_the_export_totals_the_tools_and_lists_each_turns() -> None:
    report = _export(
        [
            TurnUsage("S", 1, 1, None, "m", tool_calls=ToolCalls.of(["Bash", "Read"])),
            TurnUsage("S", 1, 1, None, "m", tool_calls=ToolCalls.of(["Bash"])),
        ]
    )
    assert report.tools == (ToolTotal("Bash", 2), ToolTotal("Read", 1))
    assert [row.tool_calls for row in report.turns] == [{"Bash": 1, "Read": 1}, {"Bash": 1}]


def _tagged(session: str, tokens: int, **tags: str) -> TurnUsage:
    return TurnUsage(session, tokens, 1, None, "m", execution_tags=ExecutionTags.from_mapping(tags))


def test_each_tag_key_is_totalled_by_value_then_its_untagged_turns() -> None:
    report = _export(
        [
            _tagged("S", 10, pipeline="review", step="2"),
            _tagged("S", 20, pipeline="review", step="1"),
            _tagged("S", 40, step="1"),
            _tagged("S", 80),
        ]
    )
    assert report.execution_tags == (
        TagTotal("pipeline", "review", 2, 30, 2, 0, 0, 0.0),
        TagTotal("pipeline", None, 2, 120, 2, 0, 0, 0.0),
        TagTotal("step", "1", 2, 60, 2, 0, 0, 0.0),
        TagTotal("step", "2", 1, 10, 1, 0, 0, 0.0),
        TagTotal("step", None, 1, 80, 1, 0, 0, 0.0),
    )
    assert report.turns[0].execution_tags == {"pipeline": "review", "step": "2"}


def test_a_job_without_tags_has_no_tag_totals() -> None:
    assert _export([_tagged("S", 10)]).execution_tags == ()


def test_the_report_narrows_to_the_turns_carrying_every_tag_asked_for() -> None:
    turns = FakeTurnStore(
        [
            _tagged("S", 10, pipeline="review", step="1"),
            _tagged("S", 20, pipeline="review", step="2"),
            _tagged("S", 40, pipeline="build", step="1"),
        ]
    )
    report = ExportUsageUseCase(FakeUsageStore({"S": 1.0}), turns, InMemoryIncidentLog()).execute(
        "JOB-1", tags=[("pipeline", "review"), ("step", "1")]
    )
    assert report.tags_filter == ("pipeline=review", "step=1")
    assert report.input_tokens == 10
    # A cost is a whole session's: none for some of its turns.
    assert report.total_usd == 0.0
    assert [session.cost_usd for session in report.sessions] == [None]
