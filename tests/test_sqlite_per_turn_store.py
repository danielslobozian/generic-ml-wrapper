# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the SQLite per-turn metering store."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_per_turn_store import (
    SqlitePerTurnStoreAdapter,
)
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStoreAdapter
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage

if TYPE_CHECKING:
    from pathlib import Path


def _store(tmp_path: Path) -> SqlitePerTurnStoreAdapter:
    return SqlitePerTurnStoreAdapter(Ledger(tmp_path / "ledger.db"))


def _seed(tmp_path: Path, job: str, *sessions: str) -> None:
    """Record the sessions a cost or a turn will be written against.

    The tables reference each other, so neither can be written for a session that was
    never recorded -- in a real run the session is persisted before the client that
    produces either is launched.
    """
    store = SqliteSessionStoreAdapter(Ledger(tmp_path / "ledger.db"))
    for session in sessions:
        store.record(Session(session, job, "claude", None))


def test_unknown_job_has_no_turns(tmp_path: Path) -> None:
    assert _store(tmp_path).turns_for_job("JOB-9") == []


def test_record_then_read_in_order(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed(tmp_path, "JOB-1", "JOB-1_001")
    first = TurnUsage("JOB-1_001", 100, 20, 0.01, "Opus 4.8", timestamp=1.0, duration_s=0.5)
    second = TurnUsage("JOB-1_001", 50, 200, None, None)
    store.record("JOB-1", first)
    store.record("JOB-1", second)
    assert store.turns_for_job("JOB-1") == [first, second]


def test_turns_are_isolated_per_job(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _seed(tmp_path, "JOB-1", "JOB-1_001")
    _seed(tmp_path, "JOB-2", "JOB-2_001")
    store.record("JOB-1", TurnUsage("JOB-1_001", 1, 2, None, None))
    store.record("JOB-2", TurnUsage("JOB-2_001", 3, 4, None, None))
    assert store.turns_for_job("JOB-1") == [TurnUsage("JOB-1_001", 1, 2, None, None)]
