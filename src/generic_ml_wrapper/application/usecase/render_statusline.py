# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The RenderStatusline use case: parse a client payload, record usage, render."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage

from generic_ml_wrapper.application.domain.service.statusline_renderer import (
    render_statusline,
    render_usage_row,
)
from generic_ml_wrapper.application.port.inbound.render_statusline import RenderStatusline
from generic_ml_wrapper.application.port.outbound.client_status import ClientStatusParserPort
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort
from generic_ml_wrapper.application.port.outbound.workspace import WorkspaceInspectorPort


class RenderStatuslineUseCase(RenderStatusline):
    """Parse the client's status payload, record its session cost, and render a line."""

    def __init__(
        self,
        parser: ClientStatusParserPort,
        usage: UsageStorePort,
        workspace: WorkspaceInspectorPort,
        turns: PerTurnMeteringPort,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            parser: The client's status-payload parser.
            usage: Where recorded session cost is persisted and read.
            workspace: The inspector for the client-agnostic environment facts.
            turns: The per-turn store, read for the job's cumulative usage footer.
            clock: Returns the current epoch seconds, for the session/job ages;
                injectable so tests are deterministic.
        """
        self._parser = parser
        self._usage = usage
        self._workspace = workspace
        self._turns = turns
        self._clock = clock

    def execute(self, payload_json: str, job: str | None, session: str | None) -> str:
        """Parse the payload, record usage, and render the status line.

        The live status is the first line; when a job is active, its cumulative
        usage (turns · tokens · cost across sessions) is appended as a footer row.

        Args:
            payload_json: The raw JSON the client piped to the status-line command.
            job: The active job, or ``None`` if unknown (usage is not recorded then).
            session: The active session, or ``None`` if unknown.

        Returns:
            The status line (one or two lines) to print.
        """
        status = self._parser.parse(_decode(payload_json))
        if job and session and status.session_cost_usd is not None:
            self._usage.record_session_cost(job, session, status.session_cost_usd)
        line = render_statusline(status, self._workspace.inspect())
        footer = self._usage_footer(job, session) if job else ""
        if not footer:
            return line
        return f"{line}\n{footer}" if line else footer

    def _usage_footer(self, job: str, session: str | None) -> str:
        """The usage rows below the live line: session, then job total across sessions.

        The current session's usage comes first; the whole-job total is added only when
        the job spans other sessions. Empty when the job has no recorded activity.
        """
        turns = self._turns.turns_for_job(job)
        costs = self._usage.session_costs(job)
        if not turns and not costs:
            return ""
        rows: list[str] = []
        if session is not None:
            session_turns = [turn for turn in turns if turn.session_id == session]
            rows.append(
                render_usage_row(
                    "session",
                    session,
                    len(session_turns),
                    _tokens(session_turns),
                    costs.get(session, 0.0),
                    self._age(session_turns),
                )
            )
            spans_other_sessions = any(turn.session_id != session for turn in turns) or any(
                other != session for other in costs
            )
            if not spans_other_sessions:
                return rows[0]
        rows.append(
            render_usage_row(
                "job",
                job,
                len(turns),
                _tokens(turns),
                round(sum(costs.values()), 2),
                self._age(turns),
            )
        )
        return "\n".join(rows)

    def _age(self, turns: Sequence[TurnUsage]) -> float | None:
        """How long ago this scope's first recorded turn was, or ``None`` when it has none.

        Measured from the first *turn* rather than from when the session was recorded:
        the status line has no session store to ask, the difference is seconds, and it
        answers the better question anyway — how long work has been going, not how long
        ago a row was written. A session launched and never prompted has no age, which
        is the honest answer rather than a zero.

        This is calendar age, not time spent: a job touched for an hour on Monday reads
        ``4d`` on Friday.
        """
        stamps = [turn.timestamp for turn in turns if turn.timestamp]
        return self._clock() - min(stamps) if stamps else None


def _tokens(turns: Sequence[TurnUsage]) -> int:
    return sum(
        turn.input_tokens + turn.output_tokens + turn.cache_creation_tokens + turn.cache_read_tokens
        for turn in turns
    )


def _decode(payload_json: str) -> dict[str, object]:
    try:
        decoded: object = json.loads(payload_json)
    except (json.JSONDecodeError, ValueError):
        return {}
    return cast("dict[str, object]", decoded) if isinstance(decoded, dict) else {}
