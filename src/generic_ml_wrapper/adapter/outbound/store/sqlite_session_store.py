# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SQLite ``SessionStorePort``: sessions in the shared ``ledger.db``.

Every job is the same kind of thing here. A job's name is its identity and the store
holds no opinion about what the job is for, so recording a session under a name that
already exists is how a job accumulates its history rather than a collision to refuse.
Hiding the one job the system names for itself is a listing concern, not this one's --
see :class:`~generic_ml_wrapper.application.domain.model.authoring_job.AuthoringJob`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.session import Session
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger


class SqliteSessionStore(SessionStorePort):
    """Persist and read sessions in the ledger."""

    def __init__(self, ledger: Ledger) -> None:
        """Bind the store to the ledger.

        Args:
            ledger: The shared SQLite ledger.
        """
        self._ledger = ledger

    def jobs(self) -> list[str]:
        """Return the ids of the jobs that have recorded sessions, sorted."""
        with self._ledger.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT job FROM sessions ORDER BY job",
            ).fetchall()
        return [row["job"] for row in rows]

    def record(self, session: Session) -> None:
        """Persist a session, creating its job if the name is new."""
        with self._ledger.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO jobs (job) VALUES (?)",
                (session.job,),
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

    def bind_uuid(self, job: str, session_id: str, uuid: str) -> None:
        """Bind an observed client-side session id to a recorded session.

        Also flips ``resumable`` on: a client that mints its own id is recorded as
        not-resumable precisely because we had no id to target, so learning one is what
        makes the session resumable. Scoped by ``job`` as well as ``session_id`` because
        the ``<job>_NNN`` id is only unique within its job.
        """
        with self._ledger.connect() as connection:
            connection.execute(
                "UPDATE sessions SET uuid = ?, resumable = 1 WHERE job = ? AND session_id = ?",
                (uuid, job, session_id),
            )

    def sessions_for_job(self, job: str) -> list[Session]:
        """Return the sessions recorded for a job, oldest first."""
        with self._ledger.connect() as connection:
            rows = connection.execute(
                "SELECT session_id, job, client, uuid, cwd, resumable, created_at "
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
                created_at=row["created_at"],
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
