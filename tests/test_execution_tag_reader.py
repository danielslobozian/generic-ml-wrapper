# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for reading the ``gmlw-execution`` object a request runs under."""

import json

from generic_ml_wrapper.application.domain.model.execution_tags import ExecutionTags
from generic_ml_wrapper.application.domain.service.execution_tag_reader import (
    read_execution_tags,
)


def _anthropic(*texts: str) -> bytes:
    """A Messages-API request whose user turns say ``texts``, oldest first."""
    messages: list[object] = []
    for text in texts:
        messages.append({"role": "user", "content": [{"type": "text", "text": text}]})
        messages.append({"role": "assistant", "content": "ok"})
    return json.dumps({"system": "be brief", "messages": messages}).encode()


def test_a_request_without_the_marker_has_no_tags() -> None:
    assert read_execution_tags(_anthropic("hello")) == ExecutionTags()


def test_the_object_gives_one_tag_per_key() -> None:
    tags = read_execution_tags(_anthropic('go gmlw-execution: {"workflow": "review", "step": "1"}'))
    assert tags.as_dict() == {"step": "1", "workflow": "review"}


def test_the_last_object_in_the_conversation_wins() -> None:
    request = _anthropic(
        'gmlw-execution: {"workflow": "review", "step": "1"}',
        "carry on",
        'now gmlw-execution : {"step": "2"}',
    )
    assert read_execution_tags(request).as_dict() == {"step": "2"}


def test_an_empty_object_ends_the_tagging() -> None:
    request = _anthropic('gmlw-execution: {"step": "1"}', "gmlw-execution: {}")
    assert read_execution_tags(request) == ExecutionTags()


def test_a_value_that_is_not_text_is_kept_as_its_json() -> None:
    tags = read_execution_tags(_anthropic('gmlw-execution: {"step": 2, "final": true}'))
    assert tags.as_dict() == {"final": "true", "step": "2"}


def test_an_unreadable_latest_object_gives_no_tags_not_an_older_one() -> None:
    request = _anthropic('gmlw-execution: {"step": "1"}', "gmlw-execution: {step: 2}")
    assert read_execution_tags(request) == ExecutionTags()


def test_the_api_format_does_not_matter() -> None:
    responses = {"input": [{"role": "user", "content": 'gmlw-execution: {"step": "3"}'}]}
    chat = {"messages": [{"role": "user", "content": 'gmlw-execution: {"step": "4"}'}]}
    assert read_execution_tags(json.dumps(responses).encode()).as_dict() == {"step": "3"}
    assert read_execution_tags(json.dumps(chat).encode()).as_dict() == {"step": "4"}


def test_a_body_that_is_not_json_has_no_tags() -> None:
    assert read_execution_tags(b'gmlw-execution: {"step": "1"} not json') == ExecutionTags()
