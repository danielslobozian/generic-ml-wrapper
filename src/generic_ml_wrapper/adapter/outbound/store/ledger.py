# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The SQLite ledger: the one ``~/.gmlw/ledger.db`` behind the store adapters.

A connection is opened per operation: WAL mode lets concurrent sessions -- and the
metering relay's threads -- read and write without a shared, thread-bound
connection, and transactions give crash-consistency for free (no temp-file dance).
Pre-1.0 the schema is a single create-from-final-state file; a schema change is a
full store reset (one user, resets freely), so real per-version migrations wait for
the 1.0 backwards-compatibility promise. See docs/storage-design.md.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE jobs (
    job        TEXT PRIMARY KEY,
    kind       TEXT NOT NULL DEFAULT 'work',   -- 'work' | 'authoring'
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE sessions (
    id         INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,           -- <job>_NNN
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


class Ledger:
    """Owns the SQLite database file and hands out ready-to-use connections."""

    def __init__(self, path: Path) -> None:
        """Bind the ledger to its database file.

        Args:
            path: The ``ledger.db`` file (created, with its parent, on first use).
        """
        self._path = path

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection]:
        """Yield a WAL connection with the schema ensured, committing on success.

        Yields:
            An open connection whose row factory is :class:`sqlite3.Row`.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=5.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            _ensure_schema(connection)
            yield connection
            connection.commit()
        finally:
            connection.close()


def _ensure_schema(connection: sqlite3.Connection) -> None:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version >= SCHEMA_VERSION:
        return
    connection.executescript(_SCHEMA)
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
