# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Read a Codex turn's usage and session id off the OpenAI Responses API wire.

Codex streams a turn as Server-Sent Events and reports usage once, in the final
``response.completed`` event's ``response.usage``. Unlike Anthropic, its
``input_tokens`` is the TOTAL input including cache reads, so fresh input is
``input_tokens - cached_tokens``.

The *request* side carries codex's own session id, which is the only way to learn it
— codex mints it internally and takes no launch flag to set it (see
:func:`read_session_id`).
"""

from __future__ import annotations

import json
from typing import cast

from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import StreamUsage

_DATA_PREFIX = "data:"


def read_usage(text: str) -> StreamUsage | None:
    """Read a turn's usage from a Codex Responses API SSE stream.

    Args:
        text: The decoded response body.

    Returns:
        The turn's usage, or ``None`` if no ``response.completed`` usage was seen.
    """
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith(_DATA_PREFIX):
            continue
        try:
            decoded: object = json.loads(line[len(_DATA_PREFIX) :].strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(decoded, dict):
            continue
        event = cast("dict[str, object]", decoded)
        if event.get("type") != "response.completed":
            continue
        usage = _usage(event.get("response"))
        if usage is not None:
            return usage
    return None


def read_session_id(text: str) -> str | None:
    """Read codex's own session id from a Responses API *request* body.

    Codex mints its session id internally and has no launch flag to set one, so the
    wire is the only place we can learn it. Every turn's request body carries it in
    ``client_metadata`` (alongside ``thread_id``, which has been identical to it in
    every sample, and ``turn_id``, which is per-turn and NOT what we want). It is
    stable for the life of a session, so the first metered turn already yields it.

    ``prompt_cache_key`` carries the same value and is the fallback: it survives a
    ``client_metadata`` rename, and reading the wrong one costs a resume, not a turn.

    Args:
        text: The decoded request body.

    Returns:
        The client-side session id, or ``None`` if the body carries none.
    """
    try:
        decoded: object = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(decoded, dict):
        return None
    request = cast("dict[str, object]", decoded)
    return _as_str(_get(request.get("client_metadata"), "session_id")) or _as_str(
        request.get("prompt_cache_key")
    )


def _usage(response: object) -> StreamUsage | None:
    if not isinstance(response, dict):
        return None
    fields = cast("dict[str, object]", response)
    usage = fields.get("usage")
    if not isinstance(usage, dict):
        return None
    tokens = cast("dict[str, object]", usage)
    total_input = _as_count(tokens.get("input_tokens"))
    output = _as_count(tokens.get("output_tokens"))
    details = tokens.get("input_tokens_details")
    cached = _as_count(_get(details, "cached_tokens"))
    cache_write = _as_count(_get(details, "cache_write_tokens"))
    return StreamUsage(
        input_tokens=max(total_input - cached, 0),  # codex input_tokens includes cache reads
        output_tokens=output,
        model=_as_str(fields.get("model")),
        cache_creation_tokens=cache_write,
        cache_read_tokens=cached,
        turn_id=_as_str(fields.get("id")),
    )


def _get(mapping: object, key: str) -> object:
    if not isinstance(mapping, dict):
        return None
    return cast("dict[str, object]", mapping).get(key)


def _as_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
