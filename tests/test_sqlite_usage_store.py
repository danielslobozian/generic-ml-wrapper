# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the SQLite usage (session-cost) store."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_usage_store import SqliteUsageStore

if TYPE_CHECKING:
    from pathlib import Path


def _store(tmp_path: Path) -> SqliteUsageStore:
    return SqliteUsageStore(Ledger(tmp_path / "ledger.db"))


def test_unknown_job_has_no_costs(tmp_path: Path) -> None:
    assert _store(tmp_path).session_costs("JOB-9") == {}


def test_record_then_read(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_session_cost("JOB-1", "JOB-1_001", 0.10)
    store.record_session_cost("JOB-1", "JOB-1_002", 0.25)
    assert store.session_costs("JOB-1") == {"JOB-1_001": 0.10, "JOB-1_002": 0.25}


def test_cost_is_monotonic_highest_wins(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_session_cost("JOB-1", "JOB-1_001", 0.50)
    store.record_session_cost("JOB-1", "JOB-1_001", 0.20)  # lower: ignored
    store.record_session_cost("JOB-1", "JOB-1_001", 0.90)  # higher: wins
    assert store.session_costs("JOB-1") == {"JOB-1_001": 0.90}


def test_costs_are_isolated_per_job(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record_session_cost("JOB-1", "JOB-1_001", 0.10)
    store.record_session_cost("JOB-2", "JOB-2_001", 0.20)
    assert store.session_costs("JOB-1") == {"JOB-1_001": 0.10}
