# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SQLite ``LedgerPurgePort``: remove a job's or a session's rows from ``ledger.db``.

Every statement of a purge runs inside one :meth:`Ledger.connect` block, which commits
only on success -- so a job never half-vanishes, leaving turns keyed to a session that
is gone. Removing a session deliberately leaves the job row: a job outlives the sessions
deleted from it, and ``next_session_id`` mints one past the highest suffix, so the gap a
delete leaves can never be reused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.ledger_purge import LedgerPurgePort

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger


class SqliteLedgerPurge(LedgerPurgePort):
    """Remove recorded rows from the ledger, one transaction per purge."""

    def __init__(self, ledger: Ledger) -> None:
        """Bind the purge to the shared SQLite ledger.

        Args:
            ledger: The shared ``ledger.db``.
        """
        self._ledger = ledger

    def purge_session(self, job: str, session: str) -> None:
        """Remove one session's row, its metered turns, and its recorded cost.

        Scoped by ``job`` as well as ``session_id`` throughout: the ``<job>_NNN`` id is
        only unique within its job, which is the same reason ``bind_uuid`` is scoped that
        way -- and here the cost of getting it wrong would be deleting a stranger's rows.
        """
        with self._ledger.connect() as connection:
            connection.execute("DELETE FROM turns WHERE job = ? AND session_id = ?", (job, session))
            connection.execute(
                "DELETE FROM session_costs WHERE job = ? AND session_id = ?", (job, session)
            )
            connection.execute(
                "DELETE FROM sessions WHERE job = ? AND session_id = ?", (job, session)
            )

    def purge_job(self, job: str) -> None:
        """Remove a job and every row recorded under it."""
        with self._ledger.connect() as connection:
            connection.execute("DELETE FROM turns WHERE job = ?", (job,))
            connection.execute("DELETE FROM session_costs WHERE job = ?", (job,))
            connection.execute("DELETE FROM sessions WHERE job = ?", (job,))
            connection.execute("DELETE FROM jobs WHERE job = ?", (job,))
