# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for extracting per-turn usage from a Codex Responses API SSE stream."""

from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import StreamUsage
from generic_ml_wrapper.adapter.outbound.gateway.openai_responses import read_session_id, read_usage

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


# ── the session id, read off the request side ──
# A real codex request body, trimmed to the metadata: the id appears in client_metadata
# (beside thread_id, identical in every sample, and turn_id, which is per-turn) and again
# as prompt_cache_key.
_REQUEST = (
    '{"model":"gpt-5.6-sol","input":[],"prompt_cache_key":"019f9f6b-9989-7502-82b7-781594cd2d5c",'
    '"client_metadata":{"x-codex-window-id":"019f9f6b-9989-7502-82b7-781594cd2d5c:0",'
    '"session_id":"019f9f6b-9989-7502-82b7-781594cd2d5c",'
    '"thread_id":"019f9f6b-9989-7502-82b7-781594cd2d5c",'
    '"turn_id":"019f9f6b-9aa7-79e2-bfb9-ec73fca6b010"}}'
)


def test_reads_the_session_id_from_client_metadata() -> None:
    assert read_session_id(_REQUEST) == "019f9f6b-9989-7502-82b7-781594cd2d5c"


def test_prefers_the_session_id_over_the_turn_id() -> None:
    # The one mistake that looks right: turn_id sits beside session_id, is the same shape,
    # shares the same timestamp prefix -- and changes every turn. Binding it would rebind
    # the session on each turn and resume nothing.
    assert read_session_id(_REQUEST) != "019f9f6b-9aa7-79e2-bfb9-ec73fca6b010"


def test_falls_back_to_the_prompt_cache_key() -> None:
    # Same value by a second name; it survives a client_metadata rename.
    assert read_session_id('{"prompt_cache_key":"019f-abc","client_metadata":{}}') == "019f-abc"


def test_a_body_without_a_session_id_yields_none() -> None:
    assert read_session_id('{"model":"gpt-5.6-sol","input":[]}') is None


def test_a_non_json_body_yields_none() -> None:
    assert read_session_id("not json at all") is None


def test_a_non_object_body_yields_none() -> None:
    assert read_session_id("[1, 2, 3]") is None


def test_an_empty_session_id_is_not_an_id() -> None:
    assert read_session_id('{"client_metadata":{"session_id":""}}') is None
