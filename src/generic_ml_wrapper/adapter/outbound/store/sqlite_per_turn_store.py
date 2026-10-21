# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SQLite ``PerTurnMeteringPort``: metered turns in the shared ``ledger.db``."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from generic_ml_wrapper.application.domain.model.tool_calls import ToolCalls
from generic_ml_wrapper.application.domain.model.turn_origin import TurnRole
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
                "cache_creation_tokens, cache_read_tokens, cost_usd, model, timestamp, duration_s, "
                "role, agent, caused_by_agent, tool_calls) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                    turn.role.value,
                    turn.agent,
                    int(turn.caused_by_agent),
                    json.dumps(turn.tool_calls.as_dict()),
                ),
            )

    def turns_for_job(self, job: str) -> list[TurnUsage]:
        """Return every recorded turn for a job, in the order recorded."""
        with self._ledger.connect() as connection:
            rows = connection.execute(
                "SELECT session_id, turn_id, input_tokens, output_tokens, cache_creation_tokens, "
                "cache_read_tokens, cost_usd, model, timestamp, duration_s, role, agent, "
                "caused_by_agent, tool_calls FROM turns WHERE job = ? ORDER BY id",
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
                role=TurnRole(row["role"]),
                agent=row["agent"],
                caused_by_agent=bool(row["caused_by_agent"]),
                tool_calls=_tool_calls(row["tool_calls"]),
            )
            for row in rows
        ]


def _tool_calls(stored: str) -> ToolCalls:
    """Read a turn's stored ``{tool: calls}``; anything unreadable counts as none."""
    try:
        decoded: object = json.loads(stored)
    except (json.JSONDecodeError, ValueError, TypeError):
        return ToolCalls()
    if not isinstance(decoded, dict):
        return ToolCalls()
    counts = cast("dict[object, object]", decoded)
    return ToolCalls.from_counts(
        {
            name: calls
            for name, calls in counts.items()
            if isinstance(name, str) and isinstance(calls, int) and not isinstance(calls, bool)
        }
    )
