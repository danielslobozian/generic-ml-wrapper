# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SQLite ``PerTurnMeteringPort``: metered turns in the shared ``ledger.db``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger


class SqlitePerTurnStore(PerTurnMeteringPort):
    """Append and read metered turns, keyed by job, in the ledger."""

    def __init__(self, ledger: Ledger) -> None:
        """Bind the store to the shared SQLite ledger."""
        self._ledger = ledger

    def record(self, job: str, turn: TurnUsage) -> None:  # noqa: ARG002  (see the docstring)
        """Append one metered turn for a job.

        The job is not stored: a turn belongs to a session, and a session id already
        determines its job. The parameter stays because it is what the caller has -- the
        metering relay knows the run it was started for -- and dropping it from the port
        would make every caller look the job up to pass nothing.

        Raises:
            sqlite3.IntegrityError: If the session is not recorded -- the schema will not
                hold a turn with no session to belong to. The relay treats a failed record
                as bookkeeping it can lose, never as a failed turn.
        """
        with self._ledger.connect() as connection:
            connection.execute(
                "INSERT INTO turns (session_id, turn_id, input_tokens, output_tokens, "
                "cache_creation_tokens, cache_read_tokens, cost_usd, model, timestamp, duration_s) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    turn.session_id,
                    turn.turn_id,
                    turn.input_tokens,
                    turn.output_tokens,
                    turn.cache_creation_tokens,
                    turn.cache_read_tokens,
                    turn.cost_usd,
                    turn.model,
                    turn.timestamp,
                    turn.duration_s,
                ),
            )

    def turns_for_job(self, job: str) -> list[TurnUsage]:
        """Return every recorded turn for a job, in the order recorded.

        Reached through the session, which is where the job is recorded: the turn holds
        only the session it belongs to.
        """
        with self._ledger.connect() as connection:
            rows = connection.execute(
                "SELECT t.session_id, t.turn_id, t.input_tokens, t.output_tokens, "
                "t.cache_creation_tokens, t.cache_read_tokens, t.cost_usd, t.model, "
                "t.timestamp, t.duration_s "
                "FROM turns t JOIN sessions s ON t.session_id = s.session_id "
                "WHERE s.job = ? ORDER BY t.id",
                (job,),
            ).fetchall()
        return [
            TurnUsage(
                row["session_id"],
                row["input_tokens"],
                row["output_tokens"],
                row["cost_usd"],
                row["model"],
                cache_creation_tokens=row["cache_creation_tokens"],
                cache_read_tokens=row["cache_read_tokens"],
                timestamp=row["timestamp"],
                duration_s=row["duration_s"],
                turn_id=row["turn_id"],
            )
            for row in rows
        ]
