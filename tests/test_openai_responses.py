# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for extracting per-turn usage from a Codex Responses API SSE stream."""

from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import StreamUsage
from generic_ml_wrapper.adapter.outbound.gateway.openai_responses import read_usage

# The usage shape from a real billed Codex turn (from the cursor-codex reference).
_STREAM = (
    'data: {"type":"response.created","response":{}}\n\n'
    'data: {"type":"response.output_text.delta","delta":"pong"}\n\n'
    'data: {"type":"response.completed","response":{"id":"resp_xyz","model":"gpt-5-codex","usage":'
    '{"input_tokens":10257,"output_tokens":17,"total_tokens":10274,'
    '"input_tokens_details":{"cached_tokens":4480,"cache_write_tokens":0},'
    '"output_tokens_details":{"reasoning_tokens":10}}}}\n\n'
)


def test_reads_usage_from_response_completed() -> None:
    assert read_usage(_STREAM) == StreamUsage(
        input_tokens=10257 - 4480,  # codex input_tokens includes cached; fresh = total - cached
        output_tokens=17,
        model="gpt-5-codex",
        cache_creation_tokens=0,
        cache_read_tokens=4480,
        turn_id="resp_xyz",
    )


def test_stream_without_completed_event_yields_none() -> None:
    assert read_usage('data: {"type":"response.created","response":{}}') is None


def test_non_sse_body_yields_none() -> None:
    assert read_usage("just some text") is None
    assert read_usage("data: not json") is None
