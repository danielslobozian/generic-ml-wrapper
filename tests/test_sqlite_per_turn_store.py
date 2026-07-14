# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the SQLite per-turn metering store."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_per_turn_store import SqlitePerTurnStore
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage

if TYPE_CHECKING:
    from pathlib import Path


def _store(tmp_path: Path) -> SqlitePerTurnStore:
    return SqlitePerTurnStore(Ledger(tmp_path / "ledger.db"))


def test_unknown_job_has_no_turns(tmp_path: Path) -> None:
    assert _store(tmp_path).turns_for_job("JOB-9") == []


def test_record_then_read_in_order(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = TurnUsage("JOB-1_001", 100, 20, 0.01, "Opus 4.8", timestamp=1.0, duration_s=0.5)
    second = TurnUsage("JOB-1_001", 50, 200, None, None)
    store.record("JOB-1", first)
    store.record("JOB-1", second)
    assert store.turns_for_job("JOB-1") == [first, second]


def test_turns_are_isolated_per_job(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.record("JOB-1", TurnUsage("JOB-1_001", 1, 2, None, None))
    store.record("JOB-2", TurnUsage("JOB-2_001", 3, 4, None, None))
    assert store.turns_for_job("JOB-1") == [TurnUsage("JOB-1_001", 1, 2, None, None)]
