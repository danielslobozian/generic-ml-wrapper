# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for extracting per-turn usage from an OpenAI Chat Completions response (vibe)."""

from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import StreamUsage
from generic_ml_wrapper.adapter.outbound.gateway.openai_chat import read_usage

# A Mistral (OpenAI Chat Completions) SSE turn: usage rides the final chunk, which
# carries an empty ``choices`` and the ``usage`` block.
_STREAM = (
    'data: {"id":"cmpl-9","model":"mistral-medium-3.5","choices":[{"delta":{"content":"pong"}}]}'
    "\n\n"
    'data: {"id":"cmpl-9","model":"mistral-medium-3.5","choices":[],'
    '"usage":{"prompt_tokens":42,"completion_tokens":3,"total_tokens":45}}\n\n'
    "data: [DONE]\n\n"
)


def test_reads_usage_from_final_stream_chunk() -> None:
    assert read_usage(_STREAM) == StreamUsage(
        input_tokens=42,
        output_tokens=3,
        model="mistral-medium-3.5",
        cache_creation_tokens=0,
        cache_read_tokens=0,
        turn_id="cmpl-9",
    )


def test_prompt_tokens_include_cache_reads() -> None:
    body = (
        'data: {"id":"cmpl-1","model":"mistral-medium-3.5","choices":[],'
        '"usage":{"prompt_tokens":1000,"completion_tokens":20,'
        '"prompt_tokens_details":{"cached_tokens":600}}}\n\n'
    )
    usage = read_usage(body)
    assert usage is not None
    assert usage.input_tokens == 400  # fresh = prompt_tokens - cached
    assert usage.cache_read_tokens == 600
    assert usage.output_tokens == 20


def test_reads_usage_from_non_streaming_json() -> None:
    body = (
        '{"id":"cmpl-7","model":"mistral-medium-3.5",'
        '"choices":[{"message":{"content":"pong"}}],'
        '"usage":{"prompt_tokens":15,"completion_tokens":2,"total_tokens":17}}'
    )
    assert read_usage(body) == StreamUsage(
        input_tokens=15,
        output_tokens=2,
        model="mistral-medium-3.5",
        cache_creation_tokens=0,
        cache_read_tokens=0,
        turn_id="cmpl-7",
    )


def test_stream_without_usage_yields_none() -> None:
    body = 'data: {"id":"cmpl-9","model":"m","choices":[{"delta":{"content":"hi"}}]}'
    assert read_usage(body) is None


def test_non_body_yields_none() -> None:
    assert read_usage("just some text") is None
    assert read_usage("data: not json") is None
