# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The SQLite implementation of :class:`StoreMigrationPort`: ordered, numbered files.

The schema lives in ``migrations/NNNN.name.sql``, one file per version, each named for
the version it brings a store *to*. A file is applied inside its own transaction
together with the version bump that records it, so a crash halfway through leaves the
store at the last version that applied cleanly and the next start resumes from there.
A file must therefore never open or close a transaction itself -- this runner owns it.

The applied version lives in a ``schema_version`` table built to hold exactly one row:
its primary key is pinned to the literal 1, so a second process seeding a brand-new
store writes nothing rather than appending a row that would later make the version
ambiguous. Stores created before this existed recorded their version in SQLite's file
header instead; the first run reads ``PRAGMA user_version`` once to seed the table from
it, and never looks at it again.

Migrations run with foreign keys off, because rebuilding a table -- create the
replacement, copy the rows, drop the original, rename -- is SQLite's documented way to
change a column, and it cannot be done with the constraints live. Ordinary connections
keep them on.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.filesystem_store_lock import FilesystemStoreLock
from generic_ml_wrapper.application.domain.model.migration_failed_error import (
    MigrationFailedError,
)
from generic_ml_wrapper.application.domain.model.store_corrupt_error import StoreCorruptError
from generic_ml_wrapper.application.domain.model.store_schema_too_new_error import (
    StoreSchemaTooNewError,
)
from generic_ml_wrapper.application.port.outbound.store_migration import (
    CURRENT_SCHEMA_VERSION,
    StoreMigrationPort,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort

#: The lineage that ships with the wrapper, beside this module.
_SHIPPED = Path(__file__).parent / "migrations"

#: Every migration transaction also bumps the version row, so one changed row is the
#: floor and is not part of what the migration itself did.
_VERSION_BUMP_ROWS = 1

_CREATE_VERSION_TABLE = (
    "CREATE TABLE IF NOT EXISTS schema_version "
    "(id INTEGER PRIMARY KEY CHECK (id = 1), version INTEGER NOT NULL)"
)


class SqliteStoreMigrationAdapter(StoreMigrationPort):
    """Bring the ledger up to date by applying the numbered migration files in order."""

    def __init__(
        self,
        connect: Callable[[], sqlite3.Connection],
        store_root: Path,
        diagnostics: DiagnosticsPort | None = None,
        migrations_dir: Path | None = None,
    ) -> None:
        """Wire the runner to the database it migrates.

        Args:
            connect: Opens a connection with no schema assumptions -- this is what runs
                before the schema is known to exist.
            store_root: The directory holding the database, where the lock file lives.
            diagnostics: Where progress is reported, or ``None`` to report nothing.
            migrations_dir: Where the lineage is read from; the shipped one by default.
                A test points this at a lineage of its own to exercise a file that fails
                or a version whose file is missing.
        """
        self._connect = connect
        self._store_root = store_root
        self._diagnostics = diagnostics
        self._migrations_dir = migrations_dir if migrations_dir is not None else _SHIPPED

    def implemented_version(self) -> int:
        """Return the highest version this runner's lineage reaches."""
        return len(self._files())

    def _files(self) -> tuple[Path, ...]:
        """Every migration file in the lineage, in version order."""
        return tuple(sorted(self._migrations_dir.glob("[0-9][0-9][0-9][0-9].*.sql")))

    def _file(self, version: int) -> Path:
        """The file that brings a store to ``version``.

        Raises:
            MigrationFailedError: If the lineage has a gap where that version should be.
        """
        for path in self._files():
            if path.name.startswith(f"{version:04d}."):
                return path
        raise MigrationFailedError(version, "no migration file ships for this version")

    def migrate_to_current(self) -> None:
        """Apply every pending migration, or do nothing if the store is current."""
        with FilesystemStoreLock(self._store_root).acquire_exclusive_blocking():
            self._migrate_under_lock()

    def _migrate_under_lock(self) -> None:
        connection = self._connect()
        try:
            # Set before any migration transaction, and for this connection only: a
            # table rebuild cannot run with the constraints live.
            connection.execute("PRAGMA foreign_keys = OFF")
            version = self._bootstrap_version(connection)
            if version > CURRENT_SCHEMA_VERSION:
                raise StoreSchemaTooNewError(version, CURRENT_SCHEMA_VERSION)
            if version == CURRENT_SCHEMA_VERSION:
                return
            if self._diagnostics:
                self._diagnostics.info(
                    "applying schema migrations",
                    from_version=version,
                    to_version=CURRENT_SCHEMA_VERSION,
                )
            for target in range(version + 1, CURRENT_SCHEMA_VERSION + 1):
                self._apply(connection, target)
        finally:
            connection.close()

    def _bootstrap_version(self, connection: sqlite3.Connection) -> int:
        """Return the store's version, seeding the tracker on first contact."""
        connection.execute(_CREATE_VERSION_TABLE)
        rows = connection.execute("SELECT version FROM schema_version").fetchall()
        if len(rows) > 1:
            raise StoreCorruptError(len(rows))
        if rows:
            return int(rows[0][0])
        prior = int(connection.execute("PRAGMA user_version").fetchone()[0])
        # Pinned to id = 1, so a process that lost the race writes nothing rather than a
        # second row -- true even without the lock that already serialises this.
        connection.execute(
            "INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, ?)", (prior,)
        )
        connection.commit()
        row = connection.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
        return int(row[0]) if row is not None else prior

    def _apply(self, connection: sqlite3.Connection, target: int) -> None:
        """Apply one file and its version bump as a single transaction."""
        path = self._file(target)
        if self._diagnostics:
            self._diagnostics.debug("applying migration", migration=path.name)
        script = path.read_text(encoding="utf-8")
        before = connection.total_changes
        try:
            # ``target`` is an integer from the shipped range, never user input.
            connection.executescript(
                f"BEGIN;\n{script}\nUPDATE schema_version SET version = {target};\nCOMMIT;"
            )
            self._report_rows_changed(path, connection.total_changes - before)
        except sqlite3.Error as error:
            connection.rollback()
            if self._diagnostics:
                self._diagnostics.error("migration failed, rolled back", version=target)
            raise MigrationFailedError(target, str(error)) from error

    def _report_rows_changed(self, path: Path, changed: int) -> None:
        """Report how many rows a migration touched, when it touched any.

        A migration that only removes rows -- discarding orphans before their parents
        become enforceable -- makes this number the answer to "how much was thrown away",
        which is the difference between discarding data and discarding it silently. A
        migration that rebuilds a table copies every row through this counter too, so the
        number means "rows this file wrote or removed", not "rows lost".
        """
        rows = changed - _VERSION_BUMP_ROWS
        if self._diagnostics and rows > 0:
            self._diagnostics.info("migration changed rows", migration=path.name, rows=rows)
