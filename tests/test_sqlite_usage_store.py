# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the SQLite usage (session-cost) store."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_usage_store import SqliteUsageStore
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.session_cost import SessionCost

if TYPE_CHECKING:
    from pathlib import Path


def _store(tmp_path: Path) -> SqliteUsageStore:
    return SqliteUsageStore(Ledger(tmp_path / "ledger.db"))


def _seed(tmp_path: Path, job: str, *sessions: str) -> None:
    """Record the sessions a cost or a turn will be written against.

    The tables reference each other, so neither can be written for a session that was
    never recorded -- in a real run the session is persisted before the client that
    produces either is launched.
    """
    store = SqliteSessionStore(Ledger(tmp_path / "ledger.db"))
    for session in sessions:
        store.record(Session(session, job, "claude", None))


def test_unknown_job_has_no_costs(tmp_path: Path) -> None:
    assert _store(tmp_path).session_costs("JOB-9") == {}


def test_record_then_read(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed(tmp_path, "JOB-1", "JOB-1_001", "JOB-1_002")
    store.record_session_cost("JOB-1", SessionCost("JOB-1_001", 0.10))
    store.record_session_cost("JOB-1", SessionCost("JOB-1_002", 0.25))
    assert store.session_costs("JOB-1") == {"JOB-1_001": 0.10, "JOB-1_002": 0.25}


def test_cost_is_monotonic_highest_wins(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed(tmp_path, "JOB-1", "JOB-1_001")
    store.record_session_cost("JOB-1", SessionCost("JOB-1_001", 0.50))
    store.record_session_cost("JOB-1", SessionCost("JOB-1_001", 0.20))  # lower: ignored
    store.record_session_cost("JOB-1", SessionCost("JOB-1_001", 0.90))  # higher: wins
    assert store.session_costs("JOB-1") == {"JOB-1_001": 0.90}


def test_costs_are_isolated_per_job(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed(tmp_path, "JOB-1", "JOB-1_001")
    _seed(tmp_path, "JOB-2", "JOB-2_001")
    store.record_session_cost("JOB-1", SessionCost("JOB-1_001", 0.10))
    store.record_session_cost("JOB-2", SessionCost("JOB-2_001", 0.20))
    assert store.session_costs("JOB-1") == {"JOB-1_001": 0.10}
