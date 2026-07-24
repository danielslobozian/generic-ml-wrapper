# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SQLite ``SessionStorePort``: sessions in the shared ``ledger.db``.

The store is scoped to a ``kind`` (``work`` or ``authoring``): recording tags the
job with it and :meth:`jobs` filters by it, so authoring sessions stay out of
``gmlw jobs`` -- the same separation the old parallel filesystem root gave, without
a second store.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger


class SqliteSessionStore(SessionStorePort):
    """Persist and read sessions in the ledger, scoped to a job ``kind``."""

    def __init__(self, ledger: Ledger, kind: str = "work") -> None:
        """Bind the store to the ledger and the job kind it owns.

        Args:
            ledger: The shared SQLite ledger.
            kind: The job kind this store records and lists (``work`` | ``authoring``).
        """
        self._ledger = ledger
        self._kind = kind

    def jobs(self) -> list[str]:
        """Return the ids of this kind's jobs that have recorded sessions, sorted."""
        with self._ledger.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT s.job FROM sessions s JOIN jobs j ON s.job = j.job "
                "WHERE j.kind = ? ORDER BY s.job",
                (self._kind,),
            ).fetchall()
        return [row["job"] for row in rows]

    def record(self, session: Session) -> None:
        """Persist a session, creating its job (tagged with this store's kind) if new."""
        with self._ledger.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO jobs (job, kind) VALUES (?, ?)",
                (session.job, self._kind),
            )
            connection.execute(
                "INSERT INTO sessions (session_id, job, client, uuid, cwd, resumable) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session.session_id,
                    session.job,
                    session.client,
                    session.uuid,
                    session.cwd,
                    int(session.resumable),
                ),
            )

    def sessions_for_job(self, job: str) -> list[Session]:
        """Return the sessions recorded for a job, oldest first."""
        with self._ledger.connect() as connection:
            rows = connection.execute(
                "SELECT session_id, job, client, uuid, cwd, resumable "
                "FROM sessions WHERE job = ? ORDER BY id",
                (job,),
            ).fetchall()
        return [
            Session(
                row["session_id"],
                row["job"],
                row["client"],
                row["uuid"],
                row["cwd"],
                bool(row["resumable"]),
            )
            for row in rows
        ]

    def ids_for_job(self, job: str) -> list[str]:
        """Return the session ids recorded for a job, oldest first."""
        return [session.session_id for session in self.sessions_for_job(job)]

    def latest_for_job(self, job: str) -> Session | None:
        """Return the most recently recorded session for a job, or ``None``."""
        sessions = self.sessions_for_job(job)
        return sessions[-1] if sessions else None
