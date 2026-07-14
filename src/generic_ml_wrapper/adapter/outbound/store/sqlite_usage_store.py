# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SQLite ``UsageStorePort``: per-session cumulative cost in the shared ``ledger.db``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger


class SqliteUsageStore(UsageStorePort):
    """Persist and read per-session cumulative cost (monotonic) in the ledger.

    Each session owns its own row, so two sessions of one job recording concurrently
    update different rows -- no read-modify-write of a shared map, no lost update.
    """

    def __init__(self, ledger: Ledger) -> None:
        """Bind the store to the shared SQLite ledger."""
        self._ledger = ledger

    def record_session_cost(self, job: str, session: str, cost_usd: float) -> None:
        """Record a session's cumulative cost, keeping the highest value seen."""
        with self._ledger.connect() as connection:
            connection.execute(
                "INSERT INTO session_costs (session_id, job, cost_usd) VALUES (?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET "
                "cost_usd = excluded.cost_usd, updated_at = datetime('now') "
                "WHERE excluded.cost_usd > session_costs.cost_usd",
                (session, job, cost_usd),
            )

    def session_costs(self, job: str) -> dict[str, float]:
        """Return the recorded cost per session for a job."""
        with self._ledger.connect() as connection:
            rows = connection.execute(
                "SELECT session_id, cost_usd FROM session_costs WHERE job = ?",
                (job,),
            ).fetchall()
        return {row["session_id"]: float(row["cost_usd"]) for row in rows}
