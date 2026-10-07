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

    def record(self, job: str, turn: TurnUsage) -> None:
        """Append one metered turn for a job."""
        with self._ledger.connect() as connection:
            connection.execute(
                "INSERT INTO turns (job, session_id, turn_id, input_tokens, output_tokens, "
                "cache_creation_tokens, cache_read_tokens, cost_usd, model, timestamp, duration_s) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job,
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
        """Return every recorded turn for a job, in the order recorded."""
        with self._ledger.connect() as connection:
            rows = connection.execute(
                "SELECT session_id, turn_id, input_tokens, output_tokens, cache_creation_tokens, "
                "cache_read_tokens, cost_usd, model, timestamp, duration_s "
                "FROM turns WHERE job = ? ORDER BY id",
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
