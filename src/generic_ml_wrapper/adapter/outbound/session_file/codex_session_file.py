# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Read a Codex rollout file -- ``~/.codex/sessions/…/rollout-…-<id>.jsonl`` -- for metadata.

Only these fields are read: each line's timestamp and type, the session's id, the model of
each turn, each request's usage record (with its thread, to tell an agent's requests from
the main conversation's), the start and end of each task with what triggered it, and each
tool call's name and call id. Text is never read.

Codex's ``input_tokens`` includes the tokens served from the cache, so the fresh input is
``input_tokens - cached_input_tokens``, as on the wire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.session_file.jsonl import count, epoch, records, text
from generic_ml_wrapper.application.domain.model.session_analysis import (
    RecordedCall,
    RecordedPrompt,
    RecordedToolCall,
    SessionRecord,
)
from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts

if TYPE_CHECKING:
    from pathlib import Path

CLIENT = "codex"
# The first record of every rollout file.
SESSION_META = "session_meta"
_TOOL_CALLS = frozenset({"custom_tool_call", "function_call"})
_TOOL_OUTPUTS = frozenset({"custom_tool_call_output", "function_call_output"})
_TASK_ENDS = frozenset({"task_complete", "turn_aborted"})


@dataclass
class _Reading:
    """What has been gathered so far from the rollout file."""

    session: str | None = None
    model: str | None = None
    first: float | None = None
    last: float | None = None
    calls: list[RecordedCall] = field(default_factory=list[RecordedCall])
    sent: dict[str, float] = field(default_factory=dict[str, float])
    answered: dict[str, float] = field(default_factory=dict[str, float])
    called: dict[str, tuple[str, float]] = field(default_factory=dict[str, tuple[str, float]])
    returned: dict[str, float] = field(default_factory=dict[str, float])


def read(path: Path) -> SessionRecord:
    """The session recorded in the Codex rollout file at ``path``.

    Args:
        path: The rollout file.

    Returns:
        The session's metadata.
    """
    reading = _Reading()
    for record in records(path):
        moment = epoch(record, "timestamp")
        if moment is not None:
            reading.first = moment if reading.first is None else min(reading.first, moment)
            reading.last = moment if reading.last is None else max(reading.last, moment)
            _gather(record, moment, reading)
    return SessionRecord(
        client=CLIENT,
        source=str(path),
        started_at=reading.first,
        ended_at=reading.last,
        calls=tuple(reading.calls),
        prompts=tuple(
            RecordedPrompt(at, reading.answered.get(turn))
            for turn, at in sorted(reading.sent.items(), key=lambda pair: pair[1])
        ),
        tool_calls=tuple(
            sorted(
                (
                    RecordedToolCall(name, at, reading.returned.get(call_id))
                    for call_id, (name, at) in reading.called.items()
                ),
                key=lambda call: call.called_at,
            )
        ),
    )


def _gather(record: object, moment: float, reading: _Reading) -> None:
    """Note what one record says: the session, the model, a request, a task or a tool call."""
    kind = text(record, "type")
    item = text(record, "payload", "type")
    turn = text(record, "payload", "turn_id")
    call_id = text(record, "payload", "call_id")
    if kind == SESSION_META:
        reading.session = text(record, "payload", "id")
    elif kind == "turn_context":
        reading.model = text(record, "payload", "model") or reading.model
    elif kind == "token_usage_record":
        reading.calls.append(_call(record, reading.session, reading.model))
    elif item == "task_started" and turn is not None and _by_user(record):
        reading.sent.setdefault(turn, moment)
    elif item in _TASK_ENDS and turn is not None:
        reading.answered.setdefault(turn, moment)
    elif item in _TOOL_CALLS and call_id is not None:
        name = text(record, "payload", "name")
        if name:
            reading.called.setdefault(call_id, (name, moment))
    elif item in _TOOL_OUTPUTS and call_id is not None:
        reading.returned.setdefault(call_id, moment)


def _call(record: object, session: str | None, model: str | None) -> RecordedCall:
    """One request from its usage record; another thread than the session's is an agent's."""
    total = count(record, "payload", "usage", "input_tokens")
    cached = count(record, "payload", "usage", "cached_input_tokens")
    thread = text(record, "payload", "thread_id")
    return RecordedCall(
        tokens=TokenCounts(
            input=max(total - cached, 0),
            output=count(record, "payload", "usage", "output_tokens"),
            cache_read=cached,
            cache_write=count(record, "payload", "usage", "cache_write_input_tokens"),
        ),
        by_agent=session is not None and thread is not None and thread != session,
        model=model,
    )


def _by_user(record: object) -> bool:
    """Whether a task was started by the user's message (rather than by codex itself)."""
    return text(record, "payload", "turn_attribution", "turn_trigger") == "user"
