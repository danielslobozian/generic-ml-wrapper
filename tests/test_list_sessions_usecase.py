# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ListSessionsUseCase use case, driven by a fake store."""

from _conformance import InMemoryPerTurnStore, InMemoryUsageStore

from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.session_cost import SessionCost
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.port.inbound.session_summary import SessionSummary
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.usecase.list_sessions import ListSessionsService


class FakeStore(SessionStorePort):
    def __init__(self, sessions: list[Session]) -> None:
        self._sessions = sessions

    def jobs(self) -> list[str]:
        return []

    def sessions_for_job(self, job: str) -> list[Session]:
        return self._sessions

    def bind_uuid(self, job: str, session_id: str, uuid: str) -> None:
        raise NotImplementedError

    def record(self, session: Session) -> None:
        raise NotImplementedError

    def ids_for_job(self, job: str) -> list[str]:
        raise NotImplementedError

    def latest_for_job(self, job: str) -> Session | None:
        raise NotImplementedError


def _use_case(
    store: SessionStorePort,
    turns: InMemoryPerTurnStore | None = None,
    usage: InMemoryUsageStore | None = None,
) -> ListSessionsService:
    """The use case with empty usage stores unless a test supplies its own."""
    return ListSessionsService(
        store, turns or InMemoryPerTurnStore(), usage or InMemoryUsageStore()
    )


def test_no_sessions_yields_empty_list() -> None:
    assert _use_case(FakeStore([])).execute("JOB-1") == []


def test_each_session_is_summarised() -> None:
    store = FakeStore(
        [
            Session("JOB-1_001", "JOB-1", "claude", "u-1"),
            Session("JOB-1_002", "JOB-1", "claude", None),
        ]
    )
    assert _use_case(store).execute("JOB-1") == [
        SessionSummary(session_id="JOB-1_001", client="claude"),
        SessionSummary(session_id="JOB-1_002", client="claude"),
    ]


def test_summary_carries_folder_resumability_and_date() -> None:
    store = FakeStore(
        [
            Session(
                "JOB-1_001",
                "JOB-1",
                "codex",
                "u-1",
                cwd="/work/svc-a",
                resumable=False,
                created_at="2026-07-24T09:30:00",
            ),
        ]
    )
    (summary,) = _use_case(store).execute("JOB-1")
    assert summary.cwd == "/work/svc-a"
    assert summary.resumable is False
    assert summary.created_at == "2026-07-24T09:30:00"


def test_each_session_carries_its_own_turn_count_and_cost() -> None:
    store = FakeStore(
        [
            Session("JOB-1_001", "JOB-1", "claude", "u-1"),
            Session("JOB-1_002", "JOB-1", "claude", "u-2"),
        ]
    )
    turns = InMemoryPerTurnStore()
    for session in ("JOB-1_001", "JOB-1_001", "JOB-1_002"):
        turns.record("JOB-1", TurnUsage(session, 10, 5, 0.01, "sonnet"))
    usage = InMemoryUsageStore()
    usage.record_session_cost("JOB-1", SessionCost("JOB-1_001", 1.25))
    usage.record_session_cost("JOB-1", SessionCost("JOB-1_002", 0.50))

    first, second = _use_case(store, turns, usage).execute("JOB-1")

    assert (first.turn_count, first.cost_usd) == (2, 1.25)
    assert (second.turn_count, second.cost_usd) == (1, 0.50)


def test_a_session_that_never_ran_a_turn_reports_zero() -> None:
    """The abandoned-at-the-prompt session: recorded like any other, but empty."""
    store = FakeStore([Session("JOB-1_001", "JOB-1", "claude", "u-1")])

    (summary,) = _use_case(store).execute("JOB-1")

    assert summary.turn_count == 0
    assert summary.cost_usd == 0.0
