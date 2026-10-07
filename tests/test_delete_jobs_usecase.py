# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the DeleteJobs use case, driven by in-memory doubles."""

import pytest
from _conformance import InMemoryPerTurnStore, InMemorySessionStore, InMemoryUsageStore
from _delete_doubles import RecordingArtifactPurge, RecordingLedgerPurge

from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.port.inbound.delete_jobs import JobFootprint
from generic_ml_wrapper.application.port.inbound.delete_sessions import NoSuchJobError
from generic_ml_wrapper.application.usecase.delete_jobs import DeleteJobsUseCase


class _Fixture:
    """Two jobs — ``alpha`` with two sessions, ``beta`` with one."""

    def __init__(self) -> None:
        self.store = InMemorySessionStore()
        self.store.record(Session("alpha_001", "alpha", "claude", "u-1"))
        self.store.record(Session("alpha_002", "alpha", "claude", "u-2"))
        self.store.record(Session("beta_001", "beta", "codex", None))
        self.turns = InMemoryPerTurnStore()
        self.usage = InMemoryUsageStore()
        self.ledger = RecordingLedgerPurge()
        self.artifacts = RecordingArtifactPurge()

    def use_case(self) -> DeleteJobsUseCase:
        return DeleteJobsUseCase(self.store, self.turns, self.usage, self.ledger, self.artifacts)


def test_preview_measures_without_removing_anything() -> None:
    fixture = _Fixture()
    fixture.turns.record("alpha", TurnUsage("alpha_001", 10, 5, 0.02, "sonnet"))
    fixture.turns.record("alpha", TurnUsage("alpha_002", 10, 5, 0.02, "sonnet"))
    fixture.usage.record_session_cost("alpha", "alpha_001", 1.00)
    fixture.usage.record_session_cost("alpha", "alpha_002", 0.50)
    fixture.artifacts.set_job_counts("alpha", contexts=2, transcript_calls=9)

    assert fixture.use_case().preview(["alpha"]) == [
        JobFootprint(
            job="alpha",
            sessions=2,
            turns=2,
            cost_usd=1.50,
            contexts=2,
            transcript_calls=9,
        )
    ]
    assert fixture.ledger.purged_jobs == []
    assert fixture.artifacts.purged_jobs == []


def test_execute_purges_every_named_job_once() -> None:
    fixture = _Fixture()

    fixture.use_case().execute(["alpha", "beta"])

    assert fixture.ledger.purged_jobs == ["alpha", "beta"]
    assert fixture.artifacts.purged_jobs == ["alpha", "beta"]


def test_a_job_is_swept_whole_not_session_by_session() -> None:
    """The folders go outright, so residue no recorded session claims goes with them."""
    fixture = _Fixture()

    fixture.use_case().execute(["alpha"])

    assert fixture.ledger.purged_sessions == []
    assert fixture.artifacts.purged_sessions == []


def test_an_unknown_job_aborts_the_whole_batch() -> None:
    fixture = _Fixture()

    with pytest.raises(NoSuchJobError):
        fixture.use_case().execute(["alpha", "nope"])

    assert fixture.ledger.purged_jobs == []
    assert fixture.artifacts.purged_jobs == []


def test_an_authoring_job_is_unreachable_through_a_work_scoped_store() -> None:
    """No guard is written for this — the injected store simply cannot see them."""
    fixture = _Fixture()

    with pytest.raises(NoSuchJobError):
        fixture.use_case().execute(["create-workflow"])


def test_an_empty_request_removes_nothing() -> None:
    fixture = _Fixture()

    assert fixture.use_case().execute([]) == []
    assert fixture.ledger.purged_jobs == []
