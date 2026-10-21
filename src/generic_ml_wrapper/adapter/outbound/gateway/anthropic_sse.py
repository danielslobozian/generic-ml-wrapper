# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Extract per-turn token usage from an Anthropic Messages SSE stream.

Anthropic streams a turn as Server-Sent Events. Usage is split across two events:
``message_start`` carries ``input_tokens`` and the model; the final
``message_delta`` carries the cumulative ``output_tokens``. This reads both from
the raw ``data:`` lines a relay tees off the response, so the relay can record a
turn without buffering or re-encoding the body.

The *request* tells a subagent's turn from the main conversation's, and a main turn an
agent caused from the others (see :func:`read_origin`).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from generic_ml_wrapper.application.domain.model.turn_origin import (
    CAUSED_BY_AGENT,
    MAIN,
    TurnOrigin,
    TurnRole,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

_DATA_PREFIX = "data:"
# Claude Code's billing line, the first system block of every request it sends,
# carries this only on a subagent's calls -- its web-search helpers included.
_SUBAGENT_MARK = "cc_is_subagent=true"
# The tools that start a Claude Code subagent (``Task`` is its older name). Their result
# is the launch's acknowledgement for a background agent, the agent's report otherwise.
_AGENT_TOOLS = frozenset({"Agent", "Task"})
# The tag a line opens with when Claude Code hands the main conversation an agent's
# report: a background agent's completion, or a subagent's hand-back. The report may
# follow a line of its own or sit inside a system reminder, so any line counts; a tag
# quoted mid-sentence does not.
_AGENT_REPORT = re.compile(r"^\s*<(?:task-notification|agent-message)\b", re.MULTILINE)


@dataclass(frozen=True)
class StreamUsage:
    """The token usage read off one Anthropic turn (session-agnostic).

    Attributes:
        input_tokens: Fresh prompt tokens from ``message_start``.
        output_tokens: Completion tokens from the final ``message_delta``.
        model: The serving model, or ``None`` if the stream omitted it.
        cache_creation_tokens: Prompt tokens written to the cache this turn.
        cache_read_tokens: Prompt tokens served from the cache this turn.
        turn_id: The provider's id for this turn, or ``None`` if unreported.
    """

    input_tokens: int
    output_tokens: int
    model: str | None
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    turn_id: str | None = None


def read_usage(text: str) -> StreamUsage | None:
    """Read a turn's usage from a raw Anthropic response body (SSE or JSON).

    Claude streams (SSE) interactively but may answer a non-interactive request
    with a single JSON envelope; this tries the streaming shape first, then the
    non-streaming one.

    Args:
        text: The decoded response body.

    Returns:
        The turn's usage, or ``None`` if none was found.
    """
    streaming = extract_usage(text.splitlines())
    return streaming if streaming is not None else _from_json(text)


def read_origin(text: str) -> TurnOrigin:
    """Read whether a Claude turn came from the main conversation or a subagent.

    Claude Code opens every request's system prompt with a billing line
    (``x-anthropic-billing-header: ...``); a subagent's adds ``cc_is_subagent=true``.
    Subagents carry no name on the wire, so the origin never has one.

    A main turn is caused by an agent when the newest message answers an agent tool
    call or carries an agent's report. Only those technical markers are read --
    tool names and a message's opening tag -- never what the messages say.

    Args:
        text: The decoded request body.

    Returns:
        An agent origin when the mark is present, else the main conversation --
        marked as caused by an agent when it is.
    """
    try:
        decoded: object = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return MAIN
    if not isinstance(decoded, dict):
        return MAIN
    request = cast("dict[str, object]", decoded)
    system = request.get("system")
    if isinstance(system, str):
        marked = _SUBAGENT_MARK in system
    elif isinstance(system, list):
        marked = any(_SUBAGENT_MARK in _block_text(block) for block in cast("list[object]", system))
    else:
        marked = False
    if marked:
        return TurnOrigin(TurnRole.AGENT)
    return CAUSED_BY_AGENT if _caused_by_agent(request.get("messages")) else MAIN


def _caused_by_agent(messages: object) -> bool:
    """Whether the newest message answers an agent tool call or carries a report."""
    if not isinstance(messages, list) or not messages:
        return False
    history = cast("list[object]", messages)
    newest = _blocks(history[-1])
    if any(_AGENT_REPORT.search(_block_text(block)) for block in newest):
        return True
    answered = {
        call
        for block in newest
        if _field(block, "type") == "tool_result"
        and (call := _as_str(_field(block, "tool_use_id"))) is not None
    }
    calls = _blocks(history[-2]) if len(history) > 1 else []
    return any(
        _field(block, "type") == "tool_use"
        and _field(block, "name") in _AGENT_TOOLS
        and _field(block, "id") in answered
        for block in calls
    )


def _blocks(message: object) -> list[object]:
    """A message's content as blocks; a plain-string content is one text block."""
    content = _field(message, "content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return cast("list[object]", content) if isinstance(content, list) else []


def _field(block: object, key: str) -> object:
    return cast("dict[str, object]", block).get(key) if isinstance(block, dict) else None


def _block_text(block: object) -> str:
    if not isinstance(block, dict):
        return ""
    text = cast("dict[str, object]", block).get("text")
    return text if isinstance(text, str) else ""


def _from_json(text: str) -> StreamUsage | None:
    try:
        decoded: object = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(decoded, dict):
        return None
    envelope = cast("dict[str, object]", decoded)
    usage = envelope.get("usage")
    input_tokens = _usage_token(usage, "input_tokens")
    output_tokens = _usage_token(usage, "output_tokens")
    if input_tokens is None and output_tokens is None:
        return None
    return StreamUsage(
        input_tokens or 0,
        output_tokens or 0,
        _as_str(envelope.get("model")),
        _usage_token(usage, "cache_creation_input_tokens") or 0,
        _usage_token(usage, "cache_read_input_tokens") or 0,
        _as_str(envelope.get("id")),
    )


def extract_usage(lines: Iterable[str]) -> StreamUsage | None:
    """Read token usage from the ``data:`` lines of an Anthropic SSE stream.

    Args:
        lines: The response's lines (``event:``/blank lines are ignored).

    Returns:
        The turn's usage, or ``None`` if no usage was seen (e.g. a non-stream
        error response).
    """
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation: int | None = None
    cache_read: int | None = None
    model: str | None = None
    turn_id: str | None = None
    for raw in lines:
        event = _data_event(raw)
        if event is None:
            continue
        kind = event.get("type")
        if kind == "message_start":
            message = event.get("message")
            if isinstance(message, dict):
                fields = cast("dict[str, object]", message)
                model = _as_str(fields.get("model"))
                turn_id = _as_str(fields.get("id"))
                usage = fields.get("usage")
                input_tokens = _usage_token(usage, "input_tokens")
                cache_creation = _usage_token(usage, "cache_creation_input_tokens")
                cache_read = _usage_token(usage, "cache_read_input_tokens")
        elif kind == "message_delta":
            seen = _usage_token(event.get("usage"), "output_tokens")
            if seen is not None:
                output_tokens = seen
    if input_tokens is None and output_tokens is None:
        return None
    return StreamUsage(
        input_tokens or 0, output_tokens or 0, model, cache_creation or 0, cache_read or 0, turn_id
    )


def _data_event(raw: str) -> dict[str, object] | None:
    line = raw.strip()
    if not line.startswith(_DATA_PREFIX):
        return None
    try:
        decoded: object = json.loads(line[len(_DATA_PREFIX) :].strip())
    except (json.JSONDecodeError, ValueError):
        return None
    return cast("dict[str, object]", decoded) if isinstance(decoded, dict) else None


def _usage_token(usage: object, key: str) -> int | None:
    if not isinstance(usage, dict):
        return None
    value = cast("dict[str, object]", usage).get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
