# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SQLite ``LedgerPurgePort``: remove a job's or a session's rows from ``ledger.db``.

A purge is one statement against the parent row. The schema declares sessions dependent
on their job and turns and costs dependent on their session, so removing the parent
removes them -- the order this module used to spell out by hand is now a property of the
tables, stated once, where nothing can reach around it.

Removing a session deliberately leaves the job row: a job outlives the sessions deleted
from it, and ``next_session_id`` mints one past the highest suffix, so the gap a delete
leaves can never be reused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.ledger_purge import LedgerPurgePort

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger


class SqliteLedgerPurgeAdapter(LedgerPurgePort):
    """Remove recorded rows from the ledger, one transaction per purge."""

    def __init__(self, ledger: Ledger) -> None:
        """Bind the purge to the shared SQLite ledger.

        Args:
            ledger: The shared ``ledger.db``.
        """
        self._ledger = ledger

    def purge_session(self, job: str, session: str) -> None:
        """Remove one session's row, and with it its metered turns and recorded cost.

        Still scoped by ``job`` as well as ``session_id``: the id is unique across the
        table, so the job adds nothing to the lookup, but it makes the statement refuse a
        pairing that does not exist rather than delete a stranger's session on a caller's
        mistake. The children go by themselves -- the schema declares them dependent.
        """
        with self._ledger.connect() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE job = ? AND session_id = ?", (job, session)
            )

    def purge_job(self, job: str) -> None:
        """Remove a job, and with it every session, turn and cost recorded under it."""
        with self._ledger.connect() as connection:
            connection.execute("DELETE FROM jobs WHERE job = ?", (job,))
