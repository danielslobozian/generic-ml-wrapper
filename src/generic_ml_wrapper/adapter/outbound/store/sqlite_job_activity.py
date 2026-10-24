# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SQLite ``JobActivityPort``: the latest turn of each job, from the ``turns`` table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.job_activity import JobActivityPort

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger


class SqliteJobActivity(JobActivityPort):
    """One grouped query over the turns, rather than reading every turn of every job."""

    def __init__(self, ledger: Ledger) -> None:
        """Bind the reader to the ledger database.

        Args:
            ledger: The ledger whose ``turns`` table this reads.
        """
        self._ledger = ledger

    def last_turn_by_job(self) -> dict[str, float]:
        """Each job's latest turn time; a turn recorded without one (``0``) does not count."""
        with self._ledger.connect() as connection:
            rows = connection.execute(
                "SELECT job, MAX(timestamp) AS last FROM turns WHERE timestamp > 0 GROUP BY job"
            ).fetchall()
        return {row["job"]: float(row["last"]) for row in rows}
