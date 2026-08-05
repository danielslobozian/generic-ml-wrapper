# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the DeleteSessionsUseCase use case, driven by in-memory doubles.

The point of interest is not that a delete deletes -- it is *when* it refuses to. A
batch is all-or-nothing, so a typo in the third id must leave the first two alone.
"""

import pytest
from _conformance import InMemoryPerTurnStore, InMemorySessionStore, InMemoryUsageStore
from _delete_doubles import FakeSessionLock, RecordingArtifactPurge, RecordingLedgerPurge

from generic_ml_wrapper.adapter.outbound.diagnostics.null_diagnostics import NullDiagnosticsAdapter
from generic_ml_wrapper.adapter.outbound.i18n.json_catalog_localizer import (
    JsonCatalogLocalizerFactory,
)
from generic_ml_wrapper.application.domain.model.no_such_job_error import NoSuchJobError
from generic_ml_wrapper.application.domain.model.no_such_session_error import NoSuchSessionError
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.session_cost import SessionCost
from generic_ml_wrapper.application.domain.model.session_running_error import SessionRunningError
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.port.inbound.session_footprint import SessionFootprint
from generic_ml_wrapper.application.port.outbound.localizer import LocalizerPort
from generic_ml_wrapper.application.usecase.delete_sessions import DeleteSessionsService


def _localizer() -> LocalizerPort:
    """The real English catalogue: these tests assert behaviour, not translations."""
    return JsonCatalogLocalizerFactory().load("en")


class _Fixture:
    """A job with three sessions, wired to recording purges."""

    def __init__(self) -> None:
        self.store = InMemorySessionStore()
        for index in (1, 2, 3):
            self.store.record(Session(f"alpha_00{index}", "alpha", "claude", f"u-{index}"))
        self.turns = InMemoryPerTurnStore()
        self.usage = InMemoryUsageStore()
        self.trace: list[str] = []
        self.ledger = RecordingLedgerPurge(self.trace)
        self.artifacts = RecordingArtifactPurge(self.trace)
        self.locks = FakeSessionLock()

    def use_case(self) -> DeleteSessionsService:
        return DeleteSessionsService(
            self.store,
            self.turns,
            self.usage,
            self.ledger,
            self.artifacts,
            self.locks,
            NullDiagnosticsAdapter(),
        )


def test_preview_measures_without_removing_anything() -> None:
    fixture = _Fixture()
    fixture.turns.record("alpha", TurnUsage("alpha_002", 10, 5, 0.02, "sonnet"))
    fixture.usage.record_session_cost("alpha", SessionCost("alpha_002", 0.75))
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


def test_a_running_session_is_refused() -> None:
    """The reason the lock exists: nothing is removed under a live client."""
    fixture = _Fixture()
    fixture.locks.running_sessions = {"alpha_002"}

    with pytest.raises(SessionRunningError) as caught:
        fixture.use_case().execute("alpha", ["alpha_002"])

    assert caught.value.session == "alpha_002"
    assert fixture.ledger.purged_sessions == []
    assert fixture.artifacts.purged_sessions == []


def test_a_stopped_sibling_of_a_running_session_is_still_removable() -> None:
    """Locking the session rather than the job is what buys this."""
    fixture = _Fixture()
    fixture.locks.running_sessions = {"alpha_002"}

    fixture.use_case().execute("alpha", ["alpha_001"])

    assert fixture.ledger.purged_sessions == [("alpha", "alpha_001")]


def test_the_claim_is_taken_before_anything_is_removed() -> None:
    fixture = _Fixture()

    fixture.use_case().execute("alpha", ["alpha_001"])

    assert fixture.locks.claimed_sessions == [("alpha", "alpha_001")]


def test_the_files_go_before_the_rows() -> None:
    """The order the whole slot turns on.

    A row can be asked for a second time; a file whose row is gone cannot be found by
    anything the tool has. So the recoverable half goes last.
    """
    fixture = _Fixture()

    fixture.use_case().execute("alpha", ["alpha_001"])

    assert fixture.trace == ["files:alpha_001", "rows:alpha_001"]


def test_a_session_whose_files_will_not_go_keeps_its_rows() -> None:
    """So it still lists, still resumes, and the same delete finishes it next time."""
    fixture = _Fixture()
    fixture.artifacts.unremovable = {"alpha_001"}

    [outcome] = fixture.use_case().execute("alpha", ["alpha_001"])

    assert outcome.removed is False
    assert fixture.ledger.purged_sessions == []


def test_a_failed_session_does_not_stop_the_batch() -> None:
    fixture = _Fixture()
    fixture.artifacts.unremovable = {"alpha_002"}

    outcome = fixture.use_case().execute("alpha", ["alpha_001", "alpha_002", "alpha_003"])

    assert [footprint.removed for footprint in outcome] == [True, False, True]
    assert fixture.ledger.purged_sessions == [("alpha", "alpha_001"), ("alpha", "alpha_003")]


def test_the_retry_finishes_what_the_first_attempt_left() -> None:
    fixture = _Fixture()
    fixture.artifacts.unremovable = {"alpha_001"}
    fixture.use_case().execute("alpha", ["alpha_001"])

    fixture.artifacts.unremovable = set()  # whatever was holding the file has let go
    [outcome] = fixture.use_case().execute("alpha", ["alpha_001"])

    assert outcome.removed is True
    assert fixture.ledger.purged_sessions == [("alpha", "alpha_001")]
