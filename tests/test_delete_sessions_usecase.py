# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the DeleteSessions use case, driven by in-memory doubles.

The point of interest is not that a delete deletes -- it is *when* it refuses to. A
batch is all-or-nothing, so a typo in the third id must leave the first two alone.
"""

import pytest
from _conformance import InMemoryPerTurnStore, InMemorySessionStore, InMemoryUsageStore
from _delete_doubles import RecordingArtifactPurge, RecordingLedgerPurge

from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.port.inbound.delete_sessions import (
    NoSuchJobError,
    NoSuchSessionError,
    SessionFootprint,
)
from generic_ml_wrapper.application.usecase.delete_sessions import DeleteSessionsUseCase


class _Fixture:
    """A job with three sessions, wired to recording purges."""

    def __init__(self) -> None:
        self.store = InMemorySessionStore()
        for index in (1, 2, 3):
            self.store.record(Session(f"alpha_00{index}", "alpha", "claude", f"u-{index}"))
        self.turns = InMemoryPerTurnStore()
        self.usage = InMemoryUsageStore()
        self.ledger = RecordingLedgerPurge()
        self.artifacts = RecordingArtifactPurge()

    def use_case(self) -> DeleteSessionsUseCase:
        return DeleteSessionsUseCase(
            self.store, self.turns, self.usage, self.ledger, self.artifacts
        )


def test_preview_measures_without_removing_anything() -> None:
    fixture = _Fixture()
    fixture.turns.record("alpha", TurnUsage("alpha_002", 10, 5, 0.02, "sonnet"))
    fixture.usage.record_session_cost("alpha", "alpha_002", 0.75)
    fixture.artifacts.set_session_counts("alpha", "alpha_002", contexts=1, transcript_calls=6)

    assert fixture.use_case().preview("alpha", ["alpha_002"]) == [
        SessionFootprint(
            job="alpha",
            session="alpha_002",
            turns=1,
            cost_usd=0.75,
            contexts=1,
            transcript_calls=6,
        )
    ]
    assert fixture.ledger.purged_sessions == []
    assert fixture.artifacts.purged_sessions == []


def test_execute_purges_rows_and_files_for_each_session() -> None:
    fixture = _Fixture()

    fixture.use_case().execute("alpha", ["alpha_001", "alpha_003"])

    assert fixture.ledger.purged_sessions == [("alpha", "alpha_001"), ("alpha", "alpha_003")]
    assert fixture.artifacts.purged_sessions == [("alpha", "alpha_001"), ("alpha", "alpha_003")]
    assert fixture.ledger.purged_jobs == []  # the job outlives sessions removed from it
    assert fixture.artifacts.purged_jobs == []


def test_execute_reports_what_it_removed() -> None:
    """The footprint is taken before the purge — afterwards there is nothing to count."""
    fixture = _Fixture()
    fixture.turns.record("alpha", TurnUsage("alpha_001", 10, 5, 0.02, "sonnet"))
    fixture.turns.record("alpha", TurnUsage("alpha_001", 10, 5, 0.02, "sonnet"))
    fixture.artifacts.set_session_counts("alpha", "alpha_001", contexts=1, transcript_calls=3)

    (removed,) = fixture.use_case().execute("alpha", ["alpha_001"])

    assert (removed.turns, removed.contexts, removed.transcript_calls) == (2, 1, 3)


def test_an_unknown_session_aborts_the_whole_batch() -> None:
    fixture = _Fixture()

    with pytest.raises(NoSuchSessionError):
        fixture.use_case().execute("alpha", ["alpha_001", "alpha_009"])

    assert fixture.ledger.purged_sessions == []
    assert fixture.artifacts.purged_sessions == []


def test_an_unknown_job_is_refused() -> None:
    fixture = _Fixture()

    with pytest.raises(NoSuchJobError):
        fixture.use_case().execute("beta", ["beta_001"])

    assert fixture.ledger.purged_sessions == []


def test_deleting_a_middle_session_leaves_its_siblings() -> None:
    """Gaps are safe: next_session_id counts past the highest suffix, never into a gap."""
    fixture = _Fixture()

    fixture.use_case().execute("alpha", ["alpha_002"])

    assert fixture.ledger.purged_sessions == [("alpha", "alpha_002")]
    assert [session.session_id for session in fixture.store.sessions_for_job("alpha")] == [
        "alpha_001",
        "alpha_002",
        "alpha_003",
    ]  # the in-memory store is a read double; the real removal is the purge above


def test_an_empty_request_removes_nothing() -> None:
    fixture = _Fixture()

    assert fixture.use_case().execute("alpha", []) == []
    assert fixture.ledger.purged_sessions == []
