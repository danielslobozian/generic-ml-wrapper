# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Turn a session's recorded metadata into the figures shown for it."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.session_analysis import (
    DurationStats,
    SessionAnalysis,
    ToolTiming,
)
from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts
from generic_ml_wrapper.application.domain.model.tool_calls import ToolCalls

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.session_analysis import SessionRecord


def analyze(record: SessionRecord, session_id: str | None = None) -> SessionAnalysis:
    """Count, total and time what ``record`` holds.

    Args:
        record: The session as its client's file records it.
        session_id: The gmlw session it belongs to, or ``None`` when run outside gmlw.

    Returns:
        The session's figures.
    """
    tokens = TokenCounts()
    for call in record.calls:
        tokens = TokenCounts(
            tokens.input + call.tokens.input,
            tokens.output + call.tokens.output,
            tokens.cache_read + call.tokens.cache_read,
            tokens.cache_write + call.tokens.cache_write,
        )
    models = Counter(call.model for call in record.calls if call.model)
    agent_turns = sum(1 for call in record.calls if call.by_agent)
    tools = ToolCalls.of(call.name for call in record.tool_calls)
    return SessionAnalysis(
        client=record.client,
        source=record.source,
        session_id=session_id,
        started_at=record.started_at,
        ended_at=record.ended_at,
        models=tuple(model for model, _ in models.most_common()),
        main_turns=len(record.calls) - agent_turns,
        agent_turns=agent_turns,
        prompts=len(record.prompts),
        tokens=tokens,
        answer_times=DurationStats.of(
            [
                prompt.answered_at - prompt.sent_at
                for prompt in record.prompts
                if prompt.answered_at is not None
            ]
        ),
        tools=tools,
        tool_times=_tool_times(record, tools),
    )


def _tool_times(record: SessionRecord, tools: ToolCalls) -> tuple[ToolTiming, ...]:
    """Each tool's call-to-result spread, in the order ``tools`` lists them."""
    durations: dict[str, list[float]] = {}
    for call in record.tool_calls:
        if call.returned_at is not None:
            durations.setdefault(call.name, []).append(call.returned_at - call.called_at)
    timings: list[ToolTiming] = []
    for name, _ in tools.counts:
        stats = DurationStats.of(durations.get(name, []))
        if stats is not None:
            timings.append(ToolTiming(name, stats))
    return tuple(timings)
