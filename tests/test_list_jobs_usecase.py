# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ListJobs use case, driven by a fake store."""

from _conformance import InMemoryJobTagStore

from generic_ml_wrapper.application.domain.model.job_order import JobOrder
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary
from generic_ml_wrapper.application.port.outbound.job_activity import JobActivityPort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.usecase.list_jobs import ListJobsUseCase


class FakeStore(SessionStorePort):
    """Sessions per job; each started at the time given, or with no start recorded."""

    def __init__(
        self, per_job: dict[str, list[str]], started: dict[str, str] | None = None
    ) -> None:
        self._per_job = per_job
        self._started = started or {}

    def jobs(self) -> list[str]:
        return sorted(self._per_job)

    def sessions_for_job(self, job: str) -> list[Session]:
        return [
            Session(sid, job, "claude", None, created_at=self._started.get(sid))
            for sid in self._per_job.get(job, [])
        ]

    def bind_uuid(self, job: str, session_id: str, uuid: str) -> None:
        raise NotImplementedError

    def record(self, session: Session) -> None:
        raise NotImplementedError

    def ids_for_job(self, job: str) -> list[str]:
        return self._per_job.get(job, [])

    def latest_for_job(self, job: str) -> Session | None:
        raise NotImplementedError


class FakeActivity(JobActivityPort):
    def __init__(self, last: dict[str, float] | None = None) -> None:
        self._last = last or {}

    def last_turn_by_job(self) -> dict[str, float]:
        return dict(self._last)


def _use_case(
    store: FakeStore, tags: InMemoryJobTagStore | None = None, last: dict[str, float] | None = None
) -> ListJobsUseCase:
    return ListJobsUseCase(store, tags or InMemoryJobTagStore(), FakeActivity(last))


def test_no_jobs_yields_empty_list() -> None:
    assert _use_case(FakeStore({})).execute() == []


def test_each_job_is_summarised_with_its_session_count() -> None:
    store = FakeStore({"JOB-2": ["JOB-2_001"], "JOB-1": ["JOB-1_001", "JOB-1_002"]})
    summaries = _use_case(store).execute()
    assert summaries == [
        JobSummary(job="JOB-1", session_count=2),
        JobSummary(job="JOB-2", session_count=1),
    ]


def _tagged() -> InMemoryJobTagStore:
    tags = InMemoryJobTagStore()
    tags.add("JOB-1", ["sprint-42", "payments"])
    tags.add("JOB-2", ["sprint-41"])
    return tags


def test_each_job_carries_its_tags() -> None:
    store = FakeStore({"JOB-1": ["JOB-1_001"], "JOB-2": ["JOB-2_001"], "JOB-3": []})
    summaries = _use_case(store, _tagged()).execute()
    assert [(s.job, s.tags) for s in summaries] == [
        ("JOB-1", ("payments", "sprint-42")),
        ("JOB-2", ("sprint-41",)),
        ("JOB-3", ()),
    ]


def test_a_tag_narrows_the_list_case_insensitively() -> None:
    store = FakeStore({"JOB-1": ["JOB-1_001"], "JOB-2": ["JOB-2_001"]})
    summaries = _use_case(store, _tagged()).execute("Sprint-42")
    assert [s.job for s in summaries] == ["JOB-1"]


def test_a_job_was_last_worked_on_at_its_latest_turn_else_its_latest_session_start() -> None:
    store = FakeStore(
        {"turned": ["t_001"], "started": ["s_001", "s_002"], "never": ["n_001"]},
        started={
            "t_001": "1970-01-01 00:00:10",
            "s_001": "1970-01-01 00:01:00",
            "s_002": "1970-01-01 00:02:00",  # the ledger writes UTC, without a zone
        },
    )

    summaries = _use_case(store, last={"turned": 500.0}).execute()

    assert [(s.job, s.last_worked_at) for s in summaries] == [
        ("never", None),
        ("started", 120.0),
        ("turned", 500.0),
    ]


def test_the_latest_worked_on_come_first_and_the_never_worked_on_last() -> None:
    store = FakeStore({"a": ["a_001"], "b": ["b_001"], "c": ["c_001"], "d": []})

    summaries = _use_case(store, last={"a": 100.0, "c": 300.0, "b": 200.0}).execute(
        order=JobOrder.RECENT
    )

    assert [s.job for s in summaries] == ["c", "b", "a", "d"]
