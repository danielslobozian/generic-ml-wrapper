# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Read a Claude Code session file -- ``~/.claude/projects/<folder>/<id>.jsonl`` -- for metadata.

The main conversation is in ``<id>.jsonl``; each agent it started has its own file in
``<id>/subagents/``. Only these fields are read: record types and timestamps, the
assistant message's id, model and usage, a content block's type and a tool call's name
and id, a tool result's id, and the markers that say who sent a user message
(``origin.kind``, ``isMeta``, ``isCompactSummary``). Text is never read.

Claude writes one record per content block of an answer, each repeating the answer's
usage, so usage is counted once per message id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from generic_ml_wrapper.adapter.outbound.session_file.jsonl import (
    JsonObject,
    count,
    epoch,
    records,
    text,
)
from generic_ml_wrapper.adapter.outbound.session_file.jsonl import (
    field as get,
)
from generic_ml_wrapper.application.domain.model.session_analysis import (
    RecordedCall,
    RecordedPrompt,
    RecordedToolCall,
    SessionRecord,
)
from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts

if TYPE_CHECKING:
    from pathlib import Path

CLIENT = "claude"
# The model Claude names on records it made up itself (an API error shown as an answer).
_NOT_A_MODEL = "<synthetic>"
# The record types that are part of the conversation; the rest are Claude's bookkeeping.
_CONVERSATION = frozenset({"user", "assistant", "system"})


@dataclass
class _Reading:
    """What has been gathered so far, across the main file and the agents' files."""

    calls: dict[str, RecordedCall] = field(default_factory=dict[str, RecordedCall])
    called: dict[str, tuple[str, float]] = field(default_factory=dict[str, tuple[str, float]])
    returned: dict[str, float] = field(default_factory=dict[str, float])
    prompts: list[RecordedPrompt] = field(default_factory=list[RecordedPrompt])
    first: float | None = None
    last: float | None = None

    def seen(self, moment: float) -> None:
        """Widen the session's span to include ``moment``."""
        self.first = moment if self.first is None else min(self.first, moment)
        self.last = moment if self.last is None else max(self.last, moment)


def read(path: Path) -> SessionRecord:
    """The session recorded in the Claude Code file at ``path``, and its agents' files.

    Args:
        path: The main conversation's ``<id>.jsonl``.

    Returns:
        The session's metadata.
    """
    reading = _Reading()
    _read_main(path, reading)
    agents = path.with_suffix("") / "subagents"
    if agents.is_dir():
        for agent in sorted(agents.glob("*.jsonl")):
            for record in records(agent):
                _gather(record, reading, by_agent=True)
    tool_calls = sorted(
        (
            RecordedToolCall(name, called_at, reading.returned.get(tool_id))
            for tool_id, (name, called_at) in reading.called.items()
        ),
        key=lambda call: call.called_at,
    )
    return SessionRecord(
        client=CLIENT,
        source=str(path),
        started_at=reading.first,
        ended_at=reading.last,
        calls=tuple(reading.calls.values()),
        prompts=tuple(reading.prompts),
        tool_calls=tuple(tool_calls),
    )


def _read_main(path: Path, reading: _Reading) -> None:
    """Read the main conversation: its requests and tool calls, and the user's prompts.

    A prompt is answered when the last conversation record before the next prompt was
    written; a prompt with nothing after it was never answered.
    """
    sent: float | None = None
    answered: float | None = None
    for record in records(path):
        moment = _gather(record, reading, by_agent=False)
        if moment is None:
            continue
        if _is_prompt(record):
            if sent is not None:
                reading.prompts.append(RecordedPrompt(sent, answered))
            sent, answered = moment, None
        elif sent is not None and moment >= sent:
            answered = moment
    if sent is not None:
        reading.prompts.append(RecordedPrompt(sent, answered))


def _gather(record: JsonObject, reading: _Reading, *, by_agent: bool) -> float | None:
    """Note a record's request, tool calls and tool results.

    Returns:
        The record's moment when it is part of the conversation, else ``None``.
    """
    moment = epoch(record, "timestamp")
    if moment is None or record.get("type") not in _CONVERSATION:
        return None
    reading.seen(moment)
    if record.get("type") == "assistant":
        _assistant(record, moment, reading, by_agent=by_agent)
    elif record.get("type") == "user":
        for block in _blocks(record):
            tool_id = text(block, "tool_use_id")
            if get(block, "type") == "tool_result" and tool_id is not None:
                reading.returned.setdefault(tool_id, moment)
    return moment


def _assistant(record: object, moment: float, reading: _Reading, *, by_agent: bool) -> None:
    """Count an answer's request once per message id, and note its tool calls."""
    message_id = text(record, "message", "id")
    if message_id is not None and message_id not in reading.calls:
        model = text(record, "message", "model")
        reading.calls[message_id] = RecordedCall(
            tokens=TokenCounts(
                input=count(record, "message", "usage", "input_tokens"),
                output=count(record, "message", "usage", "output_tokens"),
                cache_read=count(record, "message", "usage", "cache_read_input_tokens"),
                cache_write=count(record, "message", "usage", "cache_creation_input_tokens"),
            ),
            by_agent=by_agent or get(record, "isSidechain") is True,
            model=None if model == _NOT_A_MODEL else model,
        )
    for block in _blocks(record):
        name = text(block, "name")
        tool_id = text(block, "id")
        if get(block, "type") == "tool_use" and name and tool_id:
            reading.called.setdefault(tool_id, (name, moment))


def _is_prompt(record: object) -> bool:
    """Whether a conversation record is a message the user sent.

    Recent files say so (``origin.kind`` is ``human``); older ones have no ``origin``, and
    there a user record is the user's unless it is Claude's own (``isMeta``), a
    compaction summary, or carries tool results.
    """
    if get(record, "type") != "user":
        return False
    kind = text(record, "origin", "kind")
    if kind is not None:
        return kind == "human"
    if get(record, "isMeta") is True or get(record, "isCompactSummary") is True:
        return False
    return not any(get(block, "type") == "tool_result" for block in _blocks(record))


def _blocks(record: object) -> list[object]:
    """The content blocks of a record's message (none when its content is plain text)."""
    content = get(record, "message", "content")
    return cast("list[object]", content) if isinstance(content, list) else []
