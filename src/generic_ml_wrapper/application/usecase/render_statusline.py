# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The RenderStatuslineUseCase use case: parse a client payload, record usage, render."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort
    from generic_ml_wrapper.application.port.outbound.localizer import LocalizerPort
from generic_ml_wrapper.application.domain.model.session_cost import SessionCost
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.domain.service.statusline_renderer import StatuslineRenderer
from generic_ml_wrapper.application.port.inbound.render_statusline import RenderStatuslineUseCase
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.run_handoff import RunHandoffPort
from generic_ml_wrapper.application.port.outbound.status_parsers import StatusParsersPort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort
from generic_ml_wrapper.application.port.outbound.workspace import WorkspaceInspectorPort


class RenderStatuslineService(RenderStatuslineUseCase):
    """Parse the client's status payload, record its session cost, and render a line."""

    def __init__(  # noqa: PLR0913, PLR0917  (its outbound ports, plus the pair that reports a refused write)
        self,
        parsers: StatusParsersPort,
        handoff: RunHandoffPort,
        usage: UsageStorePort,
        workspace: WorkspaceInspectorPort,
        turns: PerTurnMeteringPort,
        diagnostics: DiagnosticsPort,
        localizer: LocalizerPort,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Wire the use case to its outbound ports.

        Args:
            parsers: Resolves the parser for whichever client was launched.
            handoff: Reports the run this status line was launched as part of.
            usage: Where recorded session cost is persisted and read.
            workspace: The inspector for the client-agnostic environment facts.
            turns: The per-turn store, read for the job's cumulative usage footer.
            diagnostics: Where a cost the store refused is reported.
            localizer: Renders that report in the language the wrapper is speaking.
            clock: Returns the current epoch seconds, for the session/job ages;
                injectable so tests are deterministic.
        """
        self._parsers = parsers
        self._handoff = handoff
        self._usage = usage
        self._workspace = workspace
        self._turns = turns
        self._diagnostics = diagnostics
        self._localizer = localizer
        self._clock = clock

    def execute(self, payload_json: str) -> str:
        """Parse the payload, record usage, and render the status line.

        The live status is the first line; when a job is active, its cumulative
        usage (turns · tokens · cost across sessions) is appended as a footer row.

        Args:
            payload_json: The raw JSON the client piped to the status-line command.

        Returns:
            The status line (one or two lines) to print.
        """
        run = self._handoff.current()
        job, session = run.job, run.session_id
        status = self._parsers.for_client(run.client).parse(_decode(payload_json))
        if job and session and status.session_cost_usd is not None:
            self._record_cost(job, SessionCost(session, status.session_cost_usd))
        line = StatuslineRenderer().render_statusline(status, self._workspace.inspect())
        footer = self._usage_footer(job, session) if job else ""
        if not footer:
            return line
        return f"{line}\n{footer}" if line else footer

    def _record_cost(self, job: str, cost: SessionCost) -> None:
        """Record the cost, and let the line render even if the store refuses it.

        The store can refuse: a cost belongs to a recorded session, and a client whose
        wrapper process died can outlive the session row it was launched under -- long
        enough to pipe one more status payload at a session that is no longer there.
        Without this the refusal would escape to the caller, whose own guard degrades the
        whole command to an empty line, and the user would watch their status bar go
        blank because a bookkeeping write failed. The same trade the metering relay
        already makes: recording is never worth the thing being recorded.
        """
        try:
            self._usage.record_session_cost(job, cost)
        except Exception as error:  # noqa: BLE001  a refused write must not blank the line
            self._diagnostics.warning(
                self._localizer.t("log.session_cost_not_recorded", error=error),
                key="log.session_cost_not_recorded",
            )

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
                StatuslineRenderer().render_usage_row(
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
            StatuslineRenderer().render_usage_row(
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
