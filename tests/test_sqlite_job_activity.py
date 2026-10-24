# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for reading each job's latest turn from the ledger."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_job_activity import SqliteJobActivity
from generic_ml_wrapper.adapter.outbound.store.sqlite_per_turn_store import SqlitePerTurnStore
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage

if TYPE_CHECKING:
    from pathlib import Path


def test_each_job_reports_its_latest_timed_turn(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.db")
    turns = SqlitePerTurnStore(ledger)
    for job, moment in (("A", 100.0), ("A", 300.0), ("B", 200.0), ("C", 0.0)):
        turns.record(job, TurnUsage(f"{job}_001", 1, 1, 0.0, "m", timestamp=moment))

    assert SqliteJobActivity(ledger).last_turn_by_job() == {"A": 300.0, "B": 200.0}


def test_an_empty_ledger_has_no_activity(tmp_path: Path) -> None:
    assert SqliteJobActivity(Ledger(tmp_path / "ledger.db")).last_turn_by_job() == {}
