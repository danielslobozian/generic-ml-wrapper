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

import pytest

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_ledger_purge import SqliteLedgerPurge
from generic_ml_wrapper.adapter.outbound.store.sqlite_per_turn_store import SqlitePerTurnStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_session_store import SqliteSessionStore
from generic_ml_wrapper.adapter.outbound.store.sqlite_usage_store import SqliteUsageStore
from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.domain.model.session_cost import SessionCost
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
            usage.record_session_cost(job, SessionCost(session_id, 1.5))
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


def test_a_session_named_under_the_wrong_job_is_not_purged(tmp_path: Path) -> None:
    """The pair has to match: a real session id under someone else's job removes nothing.

    A session id is unique across the table, so the job in the statement is not what finds
    the row -- it is what stops a caller that paired the two wrongly from deleting a
    stranger's session and everything hanging off it.
    """
    ledger = _seed(tmp_path)

    SqliteLedgerPurge(ledger).purge_session("beta", "alpha_001")

    assert "alpha_001" in _rows(ledger, "sessions", "session_id")
    assert _rows(ledger, "turns", "session_id").count("alpha_001") == 2


def test_purging_a_session_takes_its_children_without_being_told_to(tmp_path: Path) -> None:
    """One statement against the session row; the schema removes what depends on it."""
    ledger = _seed(tmp_path)

    with ledger.connect() as connection:
        connection.execute("DELETE FROM sessions WHERE session_id = 'alpha_001'")

    assert "alpha_001" not in _rows(ledger, "turns", "session_id")
    assert "alpha_001" not in _rows(ledger, "session_costs", "session_id")


def test_a_turn_cannot_name_a_session_that_does_not_exist(tmp_path: Path) -> None:
    """The refusal the whole slot is for: no row may name a parent that is not there."""
    ledger = _seed(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        SqlitePerTurnStore(ledger).record("alpha", TurnUsage("alpha_404", 1, 1, 0.0, None))


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
