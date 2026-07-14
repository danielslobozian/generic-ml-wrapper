# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Extract per-turn token usage from an Anthropic Messages SSE stream.

Anthropic streams a turn as Server-Sent Events. Usage is split across two events:
``message_start`` carries ``input_tokens`` and the model; the final
``message_delta`` carries the cumulative ``output_tokens``. This reads both from
the raw ``data:`` lines a relay tees off the response, so the relay can record a
turn without buffering or re-encoding the body.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

_DATA_PREFIX = "data:"


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
