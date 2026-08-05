# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the SQLite session store."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStoreAdapter
from generic_ml_wrapper.application.domain.model.session import Session

if TYPE_CHECKING:
    from pathlib import Path


def _store(tmp_path: Path) -> SqliteSessionStoreAdapter:
    return SqliteSessionStoreAdapter(Ledger(tmp_path / "ledger.db"))


def test_unknown_job_is_empty(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.ids_for_job("JOB-1") == []
    assert store.latest_for_job("JOB-1") is None
    assert store.sessions_for_job("JOB-9") == []


def test_record_then_read_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = Session("JOB-1_001", "JOB-1", "claude", "uuid-1")
    second = Session("JOB-1_002", "JOB-1", "claude", None)
    store.record(first)
    store.record(second)

    assert store.sessions_for_job("JOB-1") == [first, second]
    assert store.ids_for_job("JOB-1") == ["JOB-1_001", "JOB-1_002"]
    assert store.latest_for_job("JOB-1") == second


def test_sessions_are_isolated_per_job(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record(Session("A_001", "A", "claude", None))
    assert store.ids_for_job("B") == []


def test_jobs_lists_recorded_jobs_sorted(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert store.jobs() == []
    store.record(Session("B_001", "B", "claude", None))
    store.record(Session("A_001", "A", "claude", None))
    assert store.jobs() == ["A", "B"]


def test_two_stores_on_one_ledger_see_the_same_jobs(tmp_path: Path) -> None:
    # The store carries no scope of its own: two instances over one ledger are one view.
    ledger = Ledger(tmp_path / "ledger.db")
    one = SqliteSessionStoreAdapter(ledger)
    another = SqliteSessionStoreAdapter(ledger)

    another.record(Session("doc-review_001", "doc-review", "claude", None))
    one.record(Session("JOB-1_001", "JOB-1", "claude", None))

    assert one.jobs() == ["JOB-1", "doc-review"]
    assert another.jobs() == ["JOB-1", "doc-review"]
    assert one.ids_for_job("doc-review") == ["doc-review_001"]
