# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ExportUsage use case, driven by fake usage stores."""

from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.port.inbound.export_usage import ModelTotal, SessionCost
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
    report = ExportUsageUseCase(FakeUsageStore({}), FakeTurnStore()).execute("JOB-1")
    assert report.job == "JOB-1"
    assert report.turns == ()
    assert report.models == ()
    assert report.session_costs == ()
    assert report.turn_count == 0
    assert report.total_usd == 0.0


def test_costs_become_sorted_session_cost_rows() -> None:
    store = FakeUsageStore({"JOB-1_002": 0.09, "JOB-1_001": 0.43})
    report = ExportUsageUseCase(store, FakeTurnStore()).execute("JOB-1")
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
    report = ExportUsageUseCase(FakeUsageStore({"JOB-1_001": 0.5}), turns).execute("JOB-1")

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
