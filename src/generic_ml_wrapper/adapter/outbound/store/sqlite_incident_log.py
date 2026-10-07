# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SQLite ``IncidentLogPort``: the ``incidents`` table of ``ledger.db``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.incident import Incident, IncidentKind
from generic_ml_wrapper.application.port.outbound.incident_log import IncidentLogPort

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger


class SqliteIncidentLog(IncidentLogPort):
    """One row per incident, appended as they happen."""

    def __init__(self, ledger: Ledger) -> None:
        """Bind the log to the ledger database.

        Args:
            ledger: The ledger whose ``incidents`` table this reads and writes.
        """
        self._ledger = ledger

    def record(self, incident: Incident) -> None:
        """Append one incident."""
        with self._ledger.connect() as connection:
            connection.execute(
                "INSERT INTO incidents (job, session_id, kind, cause, occurred_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    incident.job,
                    incident.session_id,
                    incident.kind.value,
                    incident.cause,
                    incident.occurred_at,
                ),
            )

    def incidents(self, job: str | None = None, since: float | None = None) -> list[Incident]:
        """Return the recorded incidents, oldest first, optionally narrowed."""
        query = "SELECT job, session_id, kind, cause, occurred_at FROM incidents WHERE 1 = 1"
        params: list[object] = []
        if job is not None:
            query += " AND job = ?"
            params.append(job)
        if since is not None:
            query += " AND occurred_at >= ?"
            params.append(since)
        with self._ledger.connect() as connection:
            rows = connection.execute(query + " ORDER BY occurred_at, id", params).fetchall()
        return [
            Incident(
                job=row["job"],
                session_id=row["session_id"],
                kind=IncidentKind(row["kind"]),
                cause=row["cause"],
                occurred_at=row["occurred_at"],
            )
            for row in rows
        ]
