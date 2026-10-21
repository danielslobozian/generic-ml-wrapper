# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for extracting per-turn usage from an Anthropic SSE stream."""

import json

import pytest

from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import (
    StreamUsage,
    extract_usage,
    read_origin,
    read_usage,
)
from generic_ml_wrapper.application.domain.model.turn_origin import (
    CAUSED_BY_AGENT,
    MAIN,
    TurnOrigin,
    TurnRole,
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


# The billing line Claude Code opens every request's system prompt with.
_BILLING = "x-anthropic-billing-header: cc_version=2.1.293.ddc; cc_entrypoint=cli;"


def _request(system: object) -> str:
    return json.dumps({"model": "claude-opus-5-5", "system": system, "messages": []})


def test_a_subagents_request_is_an_agent_turn() -> None:
    system = [{"type": "text", "text": _BILLING + " cc_is_subagent=true;"}, {"text": "You are"}]
    assert read_origin(_request(system)) == TurnOrigin(TurnRole.AGENT)


def test_the_mark_in_a_plain_string_system_counts_too() -> None:
    assert read_origin(_request(_BILLING + " cc_is_subagent=true;")) == TurnOrigin(TurnRole.AGENT)


@pytest.mark.parametrize(
    "body",
    [
        _request([{"type": "text", "text": _BILLING}, {"type": "text", "text": "You are"}]),
        json.dumps({"model": "claude-haiku-4-5", "messages": []}),  # startup call: no system
        _request([1, {"text": 2}]),  # malformed blocks
        "not json",
        "[]",
    ],
)
def test_anything_else_is_the_main_conversation(body: str) -> None:
    assert read_origin(body) == MAIN


def _conversation(*messages: object) -> str:
    system = [{"type": "text", "text": _BILLING}]
    return json.dumps({"model": "claude-opus-5-5", "system": system, "messages": list(messages)})


def _calls(*names: str) -> dict[str, object]:
    blocks: list[dict[str, object]] = [
        {"type": "tool_use", "id": f"call_{n}", "name": n, "input": {}} for n in names
    ]
    return {"role": "assistant", "content": blocks}


def _results(*names: str) -> dict[str, object]:
    blocks = [{"type": "tool_result", "tool_use_id": f"call_{n}", "content": "x"} for n in names]
    return {"role": "user", "content": blocks}


@pytest.mark.parametrize(
    "newest",
    [
        {"role": "user", "content": "<task-notification>\n<task-id>a1</task-id>"},
        {"role": "user", "content": [{"type": "text", "text": "  <agent-message from=x>"}]},
        {"role": "user", "content": "A session sent a message:\n<agent-message from=x>\n..."},
        {"role": "user", "content": "<system-reminder>\nNotice\n<task-notification>\n</x>"},
    ],
)
def test_an_agents_report_causes_the_main_turn(newest: object) -> None:
    assert read_origin(_conversation({"role": "user", "content": "go"}, newest)) == (
        CAUSED_BY_AGENT
    )


@pytest.mark.parametrize("tool", ["Agent", "Task"])
def test_the_result_of_an_agent_call_causes_the_main_turn(tool: str) -> None:
    body = _conversation({"role": "user", "content": "go"}, _calls(tool, "Bash"), _results(tool))
    assert read_origin(body) == CAUSED_BY_AGENT


@pytest.mark.parametrize(
    "messages",
    [
        ({"role": "user", "content": "go"},),  # the user's own prompt
        ({"role": "user", "content": "go"}, _calls("Bash"), _results("Bash")),  # another tool
        ({"role": "user", "content": "quoting <task-notification> in a prompt"},),
        (_calls("Agent"), {"role": "user", "content": "go"}),  # an older agent call
        (_results("Agent"),),  # a result without its call
    ],
)
def test_other_main_turns_are_not_caused_by_an_agent(messages: tuple[object, ...]) -> None:
    assert read_origin(_conversation(*messages)) == MAIN


def test_a_subagents_own_turn_is_never_marked_as_caused() -> None:
    system = [{"type": "text", "text": _BILLING + " cc_is_subagent=true;"}]
    body = json.dumps({"system": system, "messages": [_calls("Agent"), _results("Agent")]})
    assert read_origin(body) == TurnOrigin(TurnRole.AGENT)
