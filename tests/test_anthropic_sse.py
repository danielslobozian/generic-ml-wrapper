# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for extracting per-turn usage from an Anthropic SSE stream."""

from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import (
    StreamUsage,
    extract_usage,
    read_usage,
)

# A representative Anthropic Messages streaming response (trimmed to the events
# that carry usage), as the lines a relay tees off the wire.
_STREAM = [
    "event: message_start",
    'data: {"type":"message_start","message":{"id":"msg_abc","model":"claude-opus-4-8",'
    '"usage":{"input_tokens":1200,"output_tokens":1}}}',
    "",
    "event: content_block_delta",
    'data: {"type":"content_block_delta","delta":{"text":"hi"}}',
    "",
    "event: message_delta",
    'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},'
    '"usage":{"output_tokens":350}}',
    "",
    "event: message_stop",
    'data: {"type":"message_stop"}',
]


def test_reads_input_output_model_and_turn_id() -> None:
    assert extract_usage(_STREAM) == StreamUsage(
        input_tokens=1200, output_tokens=350, model="claude-opus-4-8", turn_id="msg_abc"
    )


def test_reads_cache_tokens_from_message_start() -> None:
    # Real shape from a live Claude turn: cache tokens dominate the input.
    stream = [
        'data: {"type":"message_start","message":{"model":"claude-opus-4-8","usage":'
        '{"input_tokens":2714,"cache_creation_input_tokens":4603,'
        '"cache_read_input_tokens":31210,"output_tokens":1}}}',
        'data: {"type":"message_delta","usage":{"output_tokens":4}}',
    ]
    assert extract_usage(stream) == StreamUsage(
        input_tokens=2714,
        output_tokens=4,
        model="claude-opus-4-8",
        cache_creation_tokens=4603,
        cache_read_tokens=31210,
    )


def test_last_message_delta_wins_for_output_tokens() -> None:
    stream = [
        'data: {"type":"message_start","message":{"model":"m","usage":{"input_tokens":10}}}',
        'data: {"type":"message_delta","usage":{"output_tokens":5}}',
        'data: {"type":"message_delta","usage":{"output_tokens":42}}',
    ]
    assert extract_usage(stream) == StreamUsage(10, 42, "m")


def test_non_stream_response_yields_none() -> None:
    assert extract_usage(['data: {"type":"error","error":{"message":"nope"}}']) is None
    assert extract_usage(["not sse", "event: ping", ""]) is None


def test_read_usage_prefers_streaming() -> None:
    assert read_usage("\n".join(_STREAM)) == StreamUsage(
        1200, 350, "claude-opus-4-8", turn_id="msg_abc"
    )


def test_read_usage_falls_back_to_non_streaming_json() -> None:
    body = '{"type":"message","model":"m","usage":{"input_tokens":7,"output_tokens":3}}'
    assert read_usage(body) == StreamUsage(7, 3, "m")


def test_read_usage_returns_none_for_unrecognized_body() -> None:
    assert read_usage("just some text") is None
    assert read_usage('{"no":"usage"}') is None


def test_malformed_data_lines_are_skipped() -> None:
    stream = [
        "data: not json",
        'data: {"type":"message_start","message":{"usage":{"input_tokens":true}}}',  # bool token
        'data: {"type":"message_delta","usage":{"output_tokens":7}}',
    ]
    # input stayed unknown (bool rejected), output read → model None
    assert extract_usage(stream) == StreamUsage(0, 7, None)
