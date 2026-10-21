# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for extracting per-turn usage from a Codex Responses API SSE stream."""

import json

import pytest

from generic_ml_wrapper.adapter.outbound.gateway.anthropic_sse import StreamUsage
from generic_ml_wrapper.adapter.outbound.gateway.openai_responses import (
    read_origin,
    read_session_id,
    read_usage,
)
from generic_ml_wrapper.application.domain.model.turn_origin import (
    CAUSED_BY_AGENT,
    MAIN,
    TurnOrigin,
    TurnRole,
)

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


def _turn_request(**turn: str) -> str:
    # client_metadata["x-codex-turn-metadata"] is itself a JSON string.
    metadata = {"session_id": "s", "x-codex-turn-metadata": json.dumps(turn)}
    return json.dumps({"model": "gpt", "client_metadata": metadata})


def test_a_spawned_agent_is_named_by_its_path_below_root() -> None:
    body = _turn_request(
        agent_name="/root/search_space", thread_source="subagent", subagent_kind="thread_spawn"
    )
    assert read_origin(body) == TurnOrigin(TurnRole.AGENT, "search_space")


def test_a_subagent_without_a_name_is_still_an_agent() -> None:
    assert read_origin(_turn_request(thread_source="subagent")) == TurnOrigin(TurnRole.AGENT)


@pytest.mark.parametrize(
    "body",
    [
        _turn_request(agent_name="/root", thread_source="user"),
        _turn_request(agent_name="/root", thread_source="thread_title"),  # its title call
        json.dumps({"model": "gpt", "client_metadata": {"session_id": "s"}}),
        json.dumps({"client_metadata": {"x-codex-turn-metadata": "not json"}}),
        "not json",
    ],
)
def test_the_root_thread_and_unreadable_requests_are_main(body: str) -> None:
    assert read_origin(body) == MAIN


def _main_request(*items: object) -> str:
    metadata = {"x-codex-turn-metadata": json.dumps({"agent_name": "/root"})}
    return json.dumps({"model": "gpt", "client_metadata": metadata, "input": list(items)})


def _call(name: str) -> dict[str, object]:
    return {"type": "function_call", "name": name, "call_id": f"c_{name}", "arguments": "{}"}


def _output(name: str) -> dict[str, object]:
    return {"type": "function_call_output", "call_id": f"c_{name}", "output": "x"}


_PROMPT: dict[str, object] = {
    "type": "message",
    "role": "user",
    "content": [{"type": "input_text", "text": "go"}],
}
_REPORT: dict[str, object] = {
    "type": "agent_message",
    "author": "/root/worker",
    "recipient": "/root",
    "content": [],
}


@pytest.mark.parametrize("tool", ["spawn_agent", "followup_task", "wait_agent", "wait"])
def test_the_result_of_an_agent_call_causes_the_main_turn(tool: str) -> None:
    body = _main_request(_PROMPT, {"type": "reasoning"}, _call(tool), _output(tool))
    assert read_origin(body) == CAUSED_BY_AGENT


def test_an_agents_message_to_the_main_thread_causes_the_main_turn() -> None:
    body = _main_request(_PROMPT, {"type": "message", "role": "assistant", "content": []}, _REPORT)
    assert read_origin(body) == CAUSED_BY_AGENT


@pytest.mark.parametrize(
    "items",
    [
        (_PROMPT,),  # the user's own prompt
        (_PROMPT, _call("exec"), _output("exec")),  # another tool
        (_call("wait_agent"), _output("wait_agent"), _call("exec"), _output("exec")),  # older
        (_PROMPT, {**_REPORT, "author": "/root"}),  # the main thread's own message
        (_call("wait_agent"), _output("wait_agent"), _PROMPT, {"type": "reasoning"}),
    ],
)
def test_other_main_turns_are_not_caused_by_an_agent(items: tuple[object, ...]) -> None:
    assert read_origin(_main_request(*items)) == MAIN


def test_the_tools_a_codex_turn_calls_are_counted_by_name() -> None:
    output = [
        {"type": "reasoning"},
        {"type": "function_call", "name": "exec", "call_id": "1"},
        {"type": "custom_tool_call", "name": "apply_patch", "call_id": "2"},
        {"type": "web_search_call", "id": "3"},
        {"type": "function_call", "name": "exec", "call_id": "4"},
        {"type": "message", "role": "assistant"},
    ]
    completed = {
        "type": "response.completed",
        "response": {"id": "r", "model": "m", "usage": {"input_tokens": 1}, "output": output},
    }
    usage = read_usage(f"data: {json.dumps(completed)}\n\n")
    assert usage is not None
    assert usage.tool_calls.as_dict() == {"exec": 2, "apply_patch": 1, "web_search": 1}
