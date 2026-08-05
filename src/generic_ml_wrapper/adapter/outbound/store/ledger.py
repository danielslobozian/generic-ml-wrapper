# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The SQLite ledger: the one ``~/.gmlw/ledger.db`` behind the store adapters.

A connection is opened per operation: WAL mode lets concurrent sessions -- and the
metering relay's threads -- read and write without a shared, thread-bound connection, and
transactions give crash-consistency for free (no temp-file dance).

The schema is not defined here. It is the ordered lineage of migration files applied by
:class:`~generic_ml_wrapper.adapter.outbound.store.sqlite_store_migration.SqliteStoreMigrationAdapter`,
and the ledger's part is only to make sure that has run before it hands out a connection
anything reads or writes through. That call is idempotent and happens once per ledger, so
a database is brought up to date by using it, not by a caller remembering to.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.sqlite_store_migration import (
    SqliteStoreMigrationAdapter,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort


class Ledger:
    """Owns the SQLite database file and hands out ready-to-use connections."""

    def __init__(self, path: Path, diagnostics: DiagnosticsPort | None = None) -> None:
        """Bind the ledger to its database file.

        Args:
            path: The ``ledger.db`` file (created, with its parent, on first use).
            diagnostics: Where migration progress is reported, or ``None`` for silence.
        """
        self._path = path
        self._migration = SqliteStoreMigrationAdapter(self._open, path.parent, diagnostics)
        self._migrated = False

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection]:
        """Yield a WAL connection with the schema up to date, committing on success.

        Yields:
            An open connection whose row factory is :class:`sqlite3.Row`.
        """
        self._ensure_migrated()
        connection = self._open()
        try:
            connection.row_factory = sqlite3.Row
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _ensure_migrated(self) -> None:
        """Run the migrations once per ledger; the runner itself is idempotent anyway."""
        if self._migrated:
            return
        self._migration.migrate_to_current()
        self._migrated = True

    def _open(self) -> sqlite3.Connection:
        """Open a connection to the database file, creating its directory if needed.

        This is what the migration runner is handed, so it must assume nothing about the
        schema -- it is what runs before there is one.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=5.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection
