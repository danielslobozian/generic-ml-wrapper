# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ledger's schema is an ordered lineage of files, and every step of it is tested.

Two properties matter more than the rest. A database created today and one carried
forward from the very first release must end in the *same* shape, because they run the
same lineage — a fresh install does not get a shortcut. And a migration that fails must
leave the store at the last version that applied cleanly, never half-way between two.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.adapter.outbound.store.sqlite_store_migration import (
    SqliteStoreMigrationAdapter,
)
from generic_ml_wrapper.application.domain.model.migration_failed_error import (
    MigrationFailedError,
)
from generic_ml_wrapper.application.domain.model.store_corrupt_error import StoreCorruptError
from generic_ml_wrapper.application.domain.model.store_schema_too_new_error import (
    StoreSchemaTooNewError,
)
from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort
from generic_ml_wrapper.application.port.outbound.store_migration import (
    CURRENT_SCHEMA_VERSION,
    StoreMigrationPort,
)

if TYPE_CHECKING:
    from collections.abc import Callable

#: The schema of the initial public commit (`dd7fe43`), transcribed here rather than read
#: from the shipped `0001` file — a fixture built out of the thing under test cannot catch
#: that thing being wrong. All four tables, because a real database has all four; an
#: earlier fixture built only two and hid a divergence between fresh and upgraded stores.
_V1_SCHEMA = """
CREATE TABLE jobs (
    job        TEXT PRIMARY KEY,
    kind       TEXT NOT NULL DEFAULT 'work',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE sessions (
    id         INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    job        TEXT NOT NULL,
    client     TEXT NOT NULL,
    uuid       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_sessions_job ON sessions(job);
CREATE TABLE turns (
    id                    INTEGER PRIMARY KEY,
    job                   TEXT NOT NULL,
    session_id            TEXT NOT NULL,
    turn_id               TEXT,
    input_tokens          INTEGER NOT NULL,
    output_tokens         INTEGER NOT NULL,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens     INTEGER NOT NULL DEFAULT 0,
    cost_usd              REAL,
    model                 TEXT,
    timestamp             REAL NOT NULL DEFAULT 0,
    duration_s            REAL NOT NULL DEFAULT 0
);
CREATE INDEX idx_turns_job ON turns(job);
CREATE TABLE session_costs (
    session_id TEXT PRIMARY KEY,
    job        TEXT NOT NULL,
    cost_usd   REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_session_costs_job ON session_costs(job);
"""


def _write_v1(path: Path) -> None:
    """A database as the first release left it: no version table, version 1 in the header."""
    connection = sqlite3.connect(path)
    connection.executescript(_V1_SCHEMA)
    connection.execute("INSERT INTO jobs (job) VALUES ('T-1')")
    insert = "INSERT INTO sessions (session_id, job, client, uuid) VALUES (?, 'T-1', ?, ?)"
    connection.execute(insert, ("T-1_001", "claude", "u1"))
    connection.execute(insert, ("T-1_002", "codex", "u2"))
    connection.execute("PRAGMA user_version = 1")
    connection.commit()
    connection.close()


def _version(path: Path) -> int:
    connection = sqlite3.connect(path)
    try:
        return int(connection.execute("SELECT version FROM schema_version").fetchone()[0])
    finally:
        connection.close()


def _columns(path: Path, table: str) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
    finally:
        connection.close()


def _connect_to(path: Path) -> Callable[[], sqlite3.Connection]:
    return lambda: sqlite3.connect(path)


def test_an_untouched_database_is_migrated_to_current(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)

    with Ledger(db).connect() as connection:
        rows = connection.execute(
            "SELECT session_id, client, cwd, resumable FROM sessions ORDER BY id"
        ).fetchall()

    assert _version(db) == CURRENT_SCHEMA_VERSION
    assert [r["session_id"] for r in rows] == ["T-1_001", "T-1_002"]  # history kept
    assert all(r["cwd"] is None for r in rows)  # added by 0002, unknown for old rows
    # 0002 backfills resumability from the client: claude yes, codex no.
    assert {r["client"]: r["resumable"] for r in rows} == {"claude": 1, "codex": 0}


def test_migrating_twice_changes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)
    with Ledger(db).connect():
        pass
    with Ledger(db).connect():  # a second ledger, a second run
        pass

    assert _version(db) == CURRENT_SCHEMA_VERSION


def test_a_fresh_database_and_an_upgraded_one_end_identical(tmp_path: Path) -> None:
    # The reason the lineage was reconstructed rather than collapsed into one file: a
    # new install runs the same steps an old database did, so neither drifts.
    fresh = tmp_path / "fresh.db"
    upgraded = tmp_path / "upgraded.db"
    _write_v1(upgraded)
    with Ledger(fresh).connect(), Ledger(upgraded).connect():
        pass

    for table in ("jobs", "sessions", "turns", "session_costs"):
        assert _columns(fresh, table) == _columns(upgraded, table)
    assert "kind" not in _columns(fresh, "jobs")  # dropped by 0004, in both


def test_the_version_is_seeded_from_the_old_header_then_owned_by_the_table(
    tmp_path: Path,
) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)  # header says 1, no schema_version table exists
    with Ledger(db).connect():
        pass

    assert _version(db) == CURRENT_SCHEMA_VERSION
    # The header is left where it was — it is read once and never written again.
    connection = sqlite3.connect(db)
    try:
        assert int(connection.execute("PRAGMA user_version").fetchone()[0]) == 1
    finally:
        connection.close()


def test_a_store_newer_than_this_build_fails_loud(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    with Ledger(db).connect():
        pass
    connection = sqlite3.connect(db)
    connection.execute("UPDATE schema_version SET version = ?", (CURRENT_SCHEMA_VERSION + 5,))
    connection.commit()
    connection.close()

    with pytest.raises(StoreSchemaTooNewError) as caught, Ledger(db).connect():
        pass

    assert caught.value.found == CURRENT_SCHEMA_VERSION + 5
    assert caught.value.supported == CURRENT_SCHEMA_VERSION


def test_a_second_version_row_cannot_be_written(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    with Ledger(db).connect():
        pass
    connection = sqlite3.connect(db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO schema_version (id, version) VALUES (2, 9)")
    finally:
        connection.close()


def test_an_ambiguous_version_fails_loud(tmp_path: Path) -> None:
    # Built by hand, because the table's own constraint refuses it: a legacy store from
    # before that constraint could still hold two rows, and guessing between them would
    # either re-run a migration or write through a mapping the tables do not match.
    db = tmp_path / "ledger.db"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE schema_version (id INTEGER, version INTEGER NOT NULL)")
    connection.executemany(
        "INSERT INTO schema_version (id, version) VALUES (?, ?)", [(1, 1), (2, 2)]
    )
    connection.commit()
    connection.close()

    with pytest.raises(StoreCorruptError) as caught, Ledger(db).connect():
        pass

    assert caught.value.rows == 2


def test_a_failing_file_rolls_back_and_leaves_the_last_good_version(tmp_path: Path) -> None:
    lineage = tmp_path / "migrations"
    lineage.mkdir()
    (lineage / "0001.good.sql").write_text("CREATE TABLE kept (a TEXT);", encoding="utf-8")
    (lineage / "0002.bad.sql").write_text(
        "CREATE TABLE gone (b TEXT);\nSELECT this_is_not_valid_sql(;", encoding="utf-8"
    )
    db = tmp_path / "ledger.db"
    migration = SqliteStoreMigrationAdapter(_connect_to(db), tmp_path, migrations_dir=lineage)

    with pytest.raises(MigrationFailedError) as caught:
        migration.migrate_to_current()

    assert caught.value.version == 2
    assert _version(db) == 1  # 0001 stands
    connection = sqlite3.connect(db)
    try:
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master")}
    finally:
        connection.close()
    assert "kept" in tables  # the file that succeeded
    assert "gone" not in tables  # the failed file left nothing behind


def test_a_gap_in_the_lineage_fails_loud(tmp_path: Path) -> None:
    lineage = tmp_path / "migrations"
    lineage.mkdir()
    (lineage / "0001.only.sql").write_text("CREATE TABLE a (x TEXT);", encoding="utf-8")
    (lineage / "0003.later.sql").write_text("CREATE TABLE c (z TEXT);", encoding="utf-8")
    db = tmp_path / "ledger.db"
    migration = SqliteStoreMigrationAdapter(_connect_to(db), tmp_path, migrations_dir=lineage)

    with pytest.raises(MigrationFailedError) as caught:
        migration.migrate_to_current()

    assert caught.value.version == 2  # the missing one, not the last one
    assert _version(db) == 1


def test_the_runner_is_a_store_migration_port(tmp_path: Path) -> None:
    migration = SqliteStoreMigrationAdapter(_connect_to(tmp_path / "ledger.db"), tmp_path)
    assert isinstance(migration, StoreMigrationPort)


def test_the_shipped_lineage_reaches_the_version_this_build_requires(tmp_path: Path) -> None:
    # The handshake that fails a build whose code and files disagree.
    migration = SqliteStoreMigrationAdapter(_connect_to(tmp_path / "ledger.db"), tmp_path)
    assert migration.implemented_version() == CURRENT_SCHEMA_VERSION


def _foreign_keys(path: Path, table: str) -> set[tuple[str, str, str]]:
    """Each reference the table declares: (its column, the parent table, the on-delete rule)."""
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(f"PRAGMA foreign_key_list({table})")
        return {(row[3], row[2], row[6]) for row in rows}
    finally:
        connection.close()


class _RecordingDiagnostics(DiagnosticsPort):
    """Keeps what the migration reported, so "and it said how many" can be asserted."""

    def __init__(self) -> None:
        self.infos: list[tuple[str, dict[str, object]]] = []

    def debug(self, message: str, **context: object) -> None: ...

    def info(self, message: str, **context: object) -> None:
        self.infos.append((message, context))

    def warning(self, message: str, **context: object) -> None: ...

    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None: ...


def test_the_relationships_are_real_after_the_migration(tmp_path: Path) -> None:
    """What the whole slot is for: every child names its parent, and cascades with it."""
    db = tmp_path / "ledger.db"
    _write_v1(db)

    with Ledger(db).connect():
        pass

    assert _foreign_keys(db, "sessions") == {("job", "jobs", "CASCADE")}
    assert _foreign_keys(db, "turns") == {("session_id", "sessions", "CASCADE")}
    assert _foreign_keys(db, "session_costs") == {("session_id", "sessions", "CASCADE")}


def test_the_redundant_job_column_is_gone_from_both_children(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)

    with Ledger(db).connect():
        pass

    assert "job" not in _columns(db, "turns")
    assert "job" not in _columns(db, "session_costs")
    assert "job" in _columns(db, "sessions")  # the one place it belongs


def test_orphaned_rows_are_discarded_and_the_count_reported(tmp_path: Path) -> None:
    """Rows predating the constraint would never be caught by it, so they go first."""
    db = tmp_path / "ledger.db"
    _write_v1(db)
    connection = sqlite3.connect(db)
    connection.execute(
        "INSERT INTO turns (job, session_id, input_tokens, output_tokens) "
        "VALUES ('T-1', 'T-1_404', 1, 1)"  # a session that was never recorded
    )
    connection.execute(
        "INSERT INTO session_costs (session_id, job, cost_usd) VALUES ('T-1_405', 'T-1', 0.5)"
    )
    connection.execute(
        "INSERT INTO sessions (session_id, job, client) VALUES ('ghost_001', 'GONE', 'claude')"
    )
    connection.commit()
    connection.close()
    diagnostics = _RecordingDiagnostics()

    SqliteStoreMigrationAdapter(_connect_to(db), tmp_path, diagnostics).migrate_to_current()

    surviving = sqlite3.connect(db)
    try:
        assert surviving.execute("SELECT count(*) FROM turns").fetchone()[0] == 0
        assert surviving.execute("SELECT count(*) FROM session_costs").fetchone()[0] == 0
        assert surviving.execute("SELECT count(*) FROM sessions").fetchone()[0] == 2
    finally:
        surviving.close()
    discards = [
        context
        for _, context in diagnostics.infos
        if context.get("migration") == "0005.discard-orphaned-rows.sql"
    ]
    assert discards == [{"migration": "0005.discard-orphaned-rows.sql", "rows": 3}]


def test_a_clean_database_reports_no_discards(tmp_path: Path) -> None:
    db = tmp_path / "ledger.db"
    _write_v1(db)
    diagnostics = _RecordingDiagnostics()

    SqliteStoreMigrationAdapter(_connect_to(db), tmp_path, diagnostics).migrate_to_current()

    assert not [
        context
        for _, context in diagnostics.infos
        if context.get("migration") == "0005.discard-orphaned-rows.sql"
    ]


def test_the_migrated_database_passes_sqlites_own_check(tmp_path: Path) -> None:
    """The check the ecosystem recommends after any migration: no violation survives."""
    db = tmp_path / "ledger.db"
    _write_v1(db)

    with Ledger(db).connect():
        pass

    connection = sqlite3.connect(db)
    try:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()
