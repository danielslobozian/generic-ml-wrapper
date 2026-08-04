# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the SQLite ledger purge.

An integration test against the real ``ledger.db`` rather than a ``_conformance`` contract
kit. The other storage ports each own their rows and can be contract-tested alone; a purge
is defined entirely by its effect on rows *three other stores* wrote, so a fake would have
to share state with three other fakes before it could assert anything. Writing through the
real stores and reading the tables back is both simpler and a stronger claim.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_ledger_purge import SqliteLedgerPurge
from generic_ml_wrapper.adapter.outbound.store.sqlite_per_turn_store import SqlitePerTurnStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_usage_store import SqliteUsageStore
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage

if TYPE_CHECKING:
    from pathlib import Path


def _seed(tmp_path: Path) -> Ledger:
    """Two jobs with two sessions each, every table populated for all four."""
    ledger = Ledger(tmp_path / "ledger.db")
    sessions = SqliteSessionStore(ledger)
    turns = SqlitePerTurnStore(ledger)
    usage = SqliteUsageStore(ledger)
    for job in ("alpha", "beta"):
        for index in (1, 2):
            session_id = f"{job}_00{index}"
            sessions.record(Session(session_id, job, "claude", f"u-{session_id}"))
            turns.record(job, TurnUsage(session_id, 10, 5, 0.02, "sonnet"))
            turns.record(job, TurnUsage(session_id, 20, 8, 0.03, "sonnet"))
            usage.record_session_cost(job, session_id, 1.5)
    return ledger


def _rows(ledger: Ledger, table: str, column: str) -> list[str]:
    with ledger.connect() as connection:
        return [row[0] for row in connection.execute(f"SELECT {column} FROM {table}").fetchall()]  # noqa: S608  (table/column are test literals, never input)


def test_purging_a_session_clears_its_rows_in_every_table(tmp_path: Path) -> None:
    ledger = _seed(tmp_path)

    SqliteLedgerPurge(ledger).purge_session("alpha", "alpha_001")

    assert "alpha_001" not in _rows(ledger, "sessions", "session_id")
    assert "alpha_001" not in _rows(ledger, "turns", "session_id")
    assert "alpha_001" not in _rows(ledger, "session_costs", "session_id")


def test_purging_a_session_leaves_its_siblings_and_its_job(tmp_path: Path) -> None:
    ledger = _seed(tmp_path)

    SqliteLedgerPurge(ledger).purge_session("alpha", "alpha_001")

    assert _rows(ledger, "sessions", "session_id") == ["alpha_002", "beta_001", "beta_002"]
    assert _rows(ledger, "turns", "session_id").count("alpha_002") == 2
    assert "alpha" in _rows(ledger, "jobs", "job")  # the job outlives the session


def test_purging_a_job_clears_every_table_including_the_job_row(tmp_path: Path) -> None:
    ledger = _seed(tmp_path)

    SqliteLedgerPurge(ledger).purge_job("alpha")

    assert _rows(ledger, "jobs", "job") == ["beta"]
    assert _rows(ledger, "sessions", "session_id") == ["beta_001", "beta_002"]
    assert set(_rows(ledger, "turns", "session_id")) == {"beta_001", "beta_002"}
    assert set(_rows(ledger, "session_costs", "session_id")) == {"beta_001", "beta_002"}


def test_purging_an_unknown_job_or_session_is_a_no_op(tmp_path: Path) -> None:
    ledger = _seed(tmp_path)
    purge = SqliteLedgerPurge(ledger)

    purge.purge_job("gamma")
    purge.purge_session("alpha", "alpha_999")

    assert len(_rows(ledger, "sessions", "session_id")) == 4


def test_a_session_id_is_only_purged_within_its_own_job(tmp_path: Path) -> None:
    """The ``<job>_NNN`` id is unique per job, so the purge is scoped by both."""
    ledger = Ledger(tmp_path / "ledger.db")
    sessions = SqliteSessionStore(ledger)
    sessions.record(Session("shared_001", "alpha", "claude", "u-1"))
    with ledger.connect() as connection:  # a same-named session under another job
        connection.execute("INSERT OR IGNORE INTO jobs (job) VALUES ('beta')")
        connection.execute(
            "INSERT INTO sessions (session_id, job, client, uuid) "
            "VALUES ('shared_001_b', 'beta', 'claude', 'u-2')"
        )
    SqlitePerTurnStore(ledger).record("beta", TurnUsage("shared_001", 1, 1, 0.0, None))

    SqliteLedgerPurge(ledger).purge_session("alpha", "shared_001")

    assert _rows(ledger, "turns", "session_id") == ["shared_001"]  # beta's turn survives
    assert _rows(ledger, "sessions", "session_id") == ["shared_001_b"]


def test_the_database_is_left_usable_after_a_purge(tmp_path: Path) -> None:
    ledger = _seed(tmp_path)

    SqliteLedgerPurge(ledger).purge_job("alpha")
    SqliteSessionStore(ledger).record(Session("alpha_003", "alpha", "claude", "u-3"))

    # Set, not sequence: a purge frees rowids and SQLite hands them straight back, so the
    # re-created job's session sorts among the survivors rather than after them.
    assert set(_rows(ledger, "sessions", "session_id")) == {"beta_001", "beta_002", "alpha_003"}
    assert SqliteSessionStore(ledger).ids_for_job("alpha") == ["alpha_003"]


def test_purging_does_not_leave_a_transaction_open(tmp_path: Path) -> None:
    """A connection opened afterwards must not find the tables locked."""
    ledger = _seed(tmp_path)

    SqliteLedgerPurge(ledger).purge_job("alpha")

    connection = sqlite3.connect(tmp_path / "ledger.db", timeout=1.0)
    try:
        assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == 2
    finally:
        connection.close()
