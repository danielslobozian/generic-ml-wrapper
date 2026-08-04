# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ledger migrations are additive: no version loses history, and none rewrites a row.

v1->v2 adds cwd/resumable. v2->v3 runs nothing at all: ``jobs.kind`` simply stopped being
written, and dropping it from an existing database would be destructive for no gain. An
upgraded database therefore keeps a dead column a fresh one never had, which is exactly
what these tests pin -- inserts must not care that it is there.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger

_V1_SESSIONS = (
    "CREATE TABLE jobs (job TEXT PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'work', "
    "created_at TEXT NOT NULL DEFAULT (datetime('now')));"
    "CREATE TABLE sessions (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL UNIQUE, "
    "job TEXT NOT NULL, client TEXT NOT NULL, uuid TEXT, "
    "created_at TEXT NOT NULL DEFAULT (datetime('now')));"
)


def _write_v1(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(_V1_SESSIONS)
    connection.execute("INSERT INTO jobs (job) VALUES ('T-1')")
    insert = "INSERT INTO sessions (session_id, job, client, uuid) VALUES (?, 'T-1', ?, ?)"
    connection.execute(insert, ("T-1_001", "claude", "u1"))
    connection.execute(insert, ("T-1_002", "codex", "u2"))
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()


def test_migration_adds_columns_and_preserves_rows(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)

    with Ledger(db).connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        rows = connection.execute(
            "SELECT session_id, client, cwd, resumable FROM sessions ORDER BY id"
        ).fetchall()

    assert version == 3  # bumped
    assert [r["session_id"] for r in rows] == ["T-1_001", "T-1_002"]  # history kept
    assert all(r["cwd"] is None for r in rows)  # new column, unknown for old rows
    # resumable backfilled from the client: claude yes, codex no.
    assert {r["client"]: r["resumable"] for r in rows} == {"claude": 1, "codex": 0}


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)
    with Ledger(db).connect():  # first open migrates
        pass
    with Ledger(db).connect() as connection:  # second open is a no-op
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert version == 3


def test_an_upgraded_database_keeps_its_dead_kind_column_and_still_accepts_jobs(
    tmp_path: Path,
) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)  # v1 already has jobs.kind; v2->v3 leaves it alone

    with Ledger(db).connect() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
        # The store no longer names the column. Its DEFAULT is what keeps this legal.
        connection.execute("INSERT OR IGNORE INTO jobs (job) VALUES ('T-2')")
        kinds = dict(connection.execute("SELECT job, kind FROM jobs ORDER BY job"))

    assert "kind" in columns  # not dropped: dropping it would be a destructive migration
    assert kinds == {"T-1": "work", "T-2": "work"}  # the old row untouched, the new defaulted


def test_a_fresh_database_has_no_kind_column(tmp_path: Path) -> None:
    with Ledger(tmp_path / "ledger.db").connect() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}

    assert "kind" not in columns
