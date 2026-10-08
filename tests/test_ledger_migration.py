# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The additive ledger migrations add columns without losing history."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.store.ledger import SCHEMA_VERSION, Ledger

_V1_SESSIONS = (
    "CREATE TABLE jobs (job TEXT PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'work', "
    "created_at TEXT NOT NULL DEFAULT (datetime('now')));"
    "CREATE TABLE sessions (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL UNIQUE, "
    "job TEXT NOT NULL, client TEXT NOT NULL, uuid TEXT, "
    "created_at TEXT NOT NULL DEFAULT (datetime('now')));"
    "CREATE TABLE turns (id INTEGER PRIMARY KEY, job TEXT NOT NULL, session_id TEXT NOT NULL, "
    "turn_id TEXT, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL, "
    "cache_creation_tokens INTEGER NOT NULL DEFAULT 0, "
    "cache_read_tokens INTEGER NOT NULL DEFAULT 0, cost_usd REAL, model TEXT, "
    "timestamp REAL NOT NULL DEFAULT 0, duration_s REAL NOT NULL DEFAULT 0);"
)


def _write_v1(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(_V1_SESSIONS)
    connection.execute("INSERT INTO jobs (job) VALUES ('T-1')")
    insert = "INSERT INTO sessions (session_id, job, client, uuid) VALUES (?, 'T-1', ?, ?)"
    connection.execute(insert, ("T-1_001", "claude", "u1"))
    connection.execute(insert, ("T-1_002", "codex", "u2"))
    connection.execute(
        "INSERT INTO turns (job, session_id, input_tokens, output_tokens) "
        "VALUES ('T-1', 'T-1_001', 10, 2)"
    )
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

    assert version == SCHEMA_VERSION  # bumped all the way
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
    assert version == SCHEMA_VERSION


def test_v2_sessions_are_kept_and_ran_no_attachment(tmp_path: Path) -> None:
    # The shape a 0.11.0 install has on disk.
    db = tmp_path / "ledger.db"
    _write_v1(db)
    connection = sqlite3.connect(db)
    connection.execute("ALTER TABLE sessions ADD COLUMN cwd TEXT")
    connection.execute("ALTER TABLE sessions ADD COLUMN resumable INTEGER NOT NULL DEFAULT 1")
    connection.execute("PRAGMA user_version = 2")
    connection.commit()
    connection.close()

    with Ledger(db).connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        rows = connection.execute(
            "SELECT session_id, attachment FROM sessions ORDER BY id"
        ).fetchall()

    assert version == SCHEMA_VERSION
    assert [(r["session_id"], r["attachment"]) for r in rows] == [
        ("T-1_001", None),
        ("T-1_002", None),
    ]


def test_v3_gains_the_job_tags_table(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)
    connection = sqlite3.connect(db)
    connection.execute("ALTER TABLE sessions ADD COLUMN cwd TEXT")
    connection.execute("ALTER TABLE sessions ADD COLUMN resumable INTEGER NOT NULL DEFAULT 1")
    connection.execute("ALTER TABLE sessions ADD COLUMN workflow TEXT")
    connection.execute("PRAGMA user_version = 3")
    connection.commit()
    connection.close()

    with Ledger(db).connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        connection.execute("INSERT INTO job_tags (job, tag) VALUES ('T-1', 'sprint-42')")
        tags = connection.execute("SELECT job, tag FROM job_tags").fetchall()

    assert version == SCHEMA_VERSION
    assert [(r["job"], r["tag"]) for r in tags] == [("T-1", "sprint-42")]


def test_v4_gains_the_incidents_table(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)
    connection = sqlite3.connect(db)
    connection.execute("ALTER TABLE sessions ADD COLUMN cwd TEXT")
    connection.execute("ALTER TABLE sessions ADD COLUMN resumable INTEGER NOT NULL DEFAULT 1")
    connection.execute("ALTER TABLE sessions ADD COLUMN workflow TEXT")
    connection.execute("CREATE TABLE job_tags (job TEXT NOT NULL, tag TEXT NOT NULL)")
    connection.execute("PRAGMA user_version = 4")
    connection.commit()
    connection.close()

    with Ledger(db).connect() as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        count = connection.execute("SELECT count(*) FROM incidents").fetchone()[0]

    assert version == SCHEMA_VERSION
    assert count == 0


def test_v5_turns_count_as_the_main_conversation(tmp_path: Path) -> None:
    # Turns recorded before agents were told apart: all the main conversation's.
    db = tmp_path / "ledger.db"
    _write_v1(db)

    with Ledger(db).connect() as connection:
        rows = connection.execute("SELECT session_id, role, agent FROM turns").fetchall()

    assert [(r["session_id"], r["role"], r["agent"]) for r in rows] == [("T-1_001", "main", None)]


def test_v6_gains_an_empty_attachments_table(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)

    with Ledger(db).connect() as connection:
        columns = [row["name"] for row in connection.execute("PRAGMA table_info(attachments)")]
        count = connection.execute("SELECT COUNT(*) FROM attachments").fetchone()[0]

    assert columns == [
        "name",
        "version",
        "description",
        "main_md_file",
        "content_hash",
        "imported_at",
    ]
    assert count == 0


def test_v7_sessions_ran_no_attachment(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)

    with Ledger(db).connect() as connection:
        rows = connection.execute(
            "SELECT attachment, attachment_version, attachment_hash FROM sessions"
        ).fetchall()

    assert rows
    assert all(tuple(row) == (None, None, None) for row in rows)


def test_v8_sessions_show_what_they_ran_before_attachments(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    with Ledger(db).connect() as connection:
        connection.execute(
            "INSERT INTO sessions (session_id, job, client, workflow) "
            "VALUES ('T-1_001', 'T-1', 'claude', 'review'), ('T-1_002', 'T-1', 'claude', NULL)"
        )
        connection.execute("PRAGMA user_version = 8")

    with Ledger(db).connect() as connection:
        rows = connection.execute(
            "SELECT attachment, attachment_version FROM sessions ORDER BY id"
        ).fetchall()

    assert [tuple(row) for row in rows] == [("review", None), (None, None)]


def test_v8_authoring_jobs_become_ordinary_jobs(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    with Ledger(db).connect() as connection:
        connection.execute("INSERT INTO jobs (job, kind) VALUES ('create-x_001', 'authoring')")
        connection.execute("PRAGMA user_version = 8")

    with Ledger(db).connect() as connection:
        kinds = [row["kind"] for row in connection.execute("SELECT kind FROM jobs")]

    assert kinds == ["work"]
