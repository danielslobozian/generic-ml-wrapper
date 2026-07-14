# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Extract per-turn token usage from an OpenAI Chat Completions response (vibe/Mistral).

Mistral's vibe CLI speaks the OpenAI Chat Completions API. Usage arrives in a
standard ``usage`` block — in the final SSE chunk when streaming (that chunk
carries ``usage`` with an empty ``choices``), or in the single JSON envelope of a
non-streaming response. ``prompt_tokens`` counts the whole input including any
cache reads, so fresh input is ``prompt_tokens - cached_tokens``.
"""

from __future__ import annotations

import json
from typing import cast

from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import StreamUsage

_DATA_PREFIX = "data:"


def read_usage(text: str) -> StreamUsage | None:
    """Read a turn's usage from an OpenAI Chat Completions response body.

    Tries the streaming shape (SSE ``data:`` lines) first, then a single
    non-streaming JSON envelope.

    Args:
        text: The decoded response body.

    Returns:
        The turn's usage, or ``None`` if none was found.
    """
    streaming = _from_sse(text)
    return streaming if streaming is not None else _from_json(text)


def _from_sse(text: str) -> StreamUsage | None:
    model: str | None = None
    turn_id: str | None = None
    tokens: tuple[int, int, int] | None = None
    for raw in text.splitlines():
        chunk = _data_event(raw)
        if chunk is None:
            continue
        model = _as_str(chunk.get("model")) or model
        turn_id = _as_str(chunk.get("id")) or turn_id
        seen = _tokens(chunk.get("usage"))
        if seen is not None:
            tokens = seen
    if tokens is None:
        return None
    fresh, output, cached = tokens
    return StreamUsage(fresh, output, model, 0, cached, turn_id)


def _from_json(text: str) -> StreamUsage | None:
    try:
        decoded: object = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(decoded, dict):
        return None
    envelope = cast("dict[str, object]", decoded)
    tokens = _tokens(envelope.get("usage"))
    if tokens is None:
        return None
    fresh, output, cached = tokens
    return StreamUsage(
        fresh, output, _as_str(envelope.get("model")), 0, cached, _as_str(envelope.get("id"))
    )


def _data_event(raw: str) -> dict[str, object] | None:
    line = raw.strip()
    if not line.startswith(_DATA_PREFIX):
        return None
    payload = line[len(_DATA_PREFIX) :].strip()
    if payload == "[DONE]":
        return None
    try:
        decoded: object = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        return None
    return cast("dict[str, object]", decoded) if isinstance(decoded, dict) else None


def _tokens(usage: object) -> tuple[int, int, int] | None:
    """Return ``(fresh_input, output, cache_read)`` from a ``usage`` block, or ``None``."""
    if not isinstance(usage, dict):
        return None
    fields = cast("dict[str, object]", usage)
    prompt = _as_count(fields.get("prompt_tokens"))
    completion = _as_count(fields.get("completion_tokens"))
    cached = _as_count(_get(fields.get("prompt_tokens_details"), "cached_tokens"))
    return (max(prompt - cached, 0), completion, cached)  # prompt_tokens includes cache reads


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
