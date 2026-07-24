# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The additive v1->v2 ledger migration adds cwd/resumable without losing history."""

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

    assert version == 2  # bumped
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
    assert version == 2
