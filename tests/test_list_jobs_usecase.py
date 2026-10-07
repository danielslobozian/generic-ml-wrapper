# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ListJobs use case, driven by a fake store."""

from _conformance import InMemoryJobTagStore

from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.usecase.list_jobs import ListJobsUseCase


class FakeStore(SessionStorePort):
    def __init__(self, per_job: dict[str, list[str]]) -> None:
        self._per_job = per_job

    def jobs(self) -> list[str]:
        return sorted(self._per_job)

    def sessions_for_job(self, job: str) -> list[Session]:
        raise NotImplementedError

    def bind_uuid(self, job: str, session_id: str, uuid: str) -> None:
        raise NotImplementedError

    def record(self, session: Session) -> None:
        raise NotImplementedError

    def ids_for_job(self, job: str) -> list[str]:
        return self._per_job.get(job, [])

    def latest_for_job(self, job: str) -> Session | None:
        raise NotImplementedError


def test_no_jobs_yields_empty_list() -> None:
    assert ListJobsUseCase(FakeStore({}), InMemoryJobTagStore()).execute() == []


def test_each_job_is_summarised_with_its_session_count() -> None:
    store = FakeStore({"JOB-2": ["JOB-2_001"], "JOB-1": ["JOB-1_001", "JOB-1_002"]})
    summaries = ListJobsUseCase(store, InMemoryJobTagStore()).execute()
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
    summaries = ListJobsUseCase(store, _tagged()).execute()
    assert [(s.job, s.tags) for s in summaries] == [
        ("JOB-1", ("payments", "sprint-42")),
        ("JOB-2", ("sprint-41",)),
        ("JOB-3", ()),
    ]


def test_a_tag_narrows_the_list_case_insensitively() -> None:
    store = FakeStore({"JOB-1": ["JOB-1_001"], "JOB-2": ["JOB-2_001"]})
    summaries = ListJobsUseCase(store, _tagged()).execute("Sprint-42")
    assert [s.job for s in summaries] == ["JOB-1"]
