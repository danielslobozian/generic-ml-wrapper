# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ListSessions use case, driven by a fake store."""

from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.port.inbound.list_sessions import SessionSummary
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.usecase.list_sessions import ListSessionsUseCase


class FakeStore(SessionStorePort):
    def __init__(self, sessions: list[Session]) -> None:
        self._sessions = sessions

    def jobs(self) -> list[str]:
        return []

    def sessions_for_job(self, job: str) -> list[Session]:
        return self._sessions

    def record(self, session: Session) -> None:
        raise NotImplementedError

    def ids_for_job(self, job: str) -> list[str]:
        raise NotImplementedError

    def latest_for_job(self, job: str) -> Session | None:
        raise NotImplementedError


def test_no_sessions_yields_empty_list() -> None:
    assert ListSessionsUseCase(FakeStore([])).execute("JOB-1") == []


def test_each_session_is_summarised() -> None:
    store = FakeStore(
        [
            Session("JOB-1_001", "JOB-1", "claude", "u-1"),
            Session("JOB-1_002", "JOB-1", "claude", None),
        ]
    )
    assert ListSessionsUseCase(store).execute("JOB-1") == [
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
    (summary,) = ListSessionsUseCase(store).execute("JOB-1")
    assert summary.cwd == "/work/svc-a"
    assert summary.resumable is False
    assert summary.created_at == "2026-07-24T09:30:00"
