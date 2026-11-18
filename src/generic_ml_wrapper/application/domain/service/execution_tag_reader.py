# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Find the ``gmlw-execution: {...}`` object a request runs under.

A client sends the whole conversation with every request, so the object a user wrote at
step 1 is still in the request at step 5. The *last* object in the request is the one in
force: writing a new one replaces the old, and ``gmlw-execution: {}`` ends the tagging.
The request alone decides, so nothing is remembered between calls.

This reads the marker and its object only -- a structural marker the user writes on
purpose -- and never interprets what the messages say.
"""

from __future__ import annotations

import json
import re
from typing import cast

from generic_ml_wrapper.application.domain.model.execution_tags import ExecutionTags

MARKER = "gmlw-execution"
_MARKER_BYTES = MARKER.encode()
_OPENING = re.compile(re.escape(MARKER) + r"\s*:\s*(?=\{)")
_DECODER = json.JSONDecoder()


def read_execution_tags(request: bytes) -> ExecutionTags:
    """The tags of the last ``gmlw-execution`` object in a request body.

    The body is read as JSON and its strings are searched in document order, so the
    format of the client's API does not matter. The object must be JSON; each value is
    kept as text (a number or a list as its JSON). An object that cannot be read gives
    no tags rather than an older one: the user's latest word is the one that counts.

    Args:
        request: The raw request body the client sent.

    Returns:
        The tags in force, or none when the request has no such object.
    """
    if _MARKER_BYTES not in request:  # the common case: no tagging at all
        return ExecutionTags()
    try:
        decoded: object = json.loads(request)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ExecutionTags()
    latest: str | None = None
    for text in _strings(decoded):
        for match in _OPENING.finditer(text):
            latest = text[match.end() :]
    return ExecutionTags() if latest is None else _tags(latest)


def _strings(node: object) -> list[str]:
    """Every string in a decoded JSON value, in document order."""
    found: list[str] = []
    stack: list[object] = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, str):
            found.append(current)
        elif isinstance(current, dict):
            stack.extend(reversed(list(cast("dict[str, object]", current).values())))
        elif isinstance(current, list):
            stack.extend(reversed(cast("list[object]", current)))
    return found


def _tags(text: str) -> ExecutionTags:
    """The tags of the JSON object ``text`` starts with; none when it is not one."""
    try:
        decoded, _ = _DECODER.raw_decode(text)
    except json.JSONDecodeError:
        return ExecutionTags()
    if not isinstance(decoded, dict):
        return ExecutionTags()
    pairs = cast("dict[str, object]", decoded)
    return ExecutionTags.from_mapping({key: _text(value) for key, value in pairs.items()})


def _text(value: object) -> str:
    """A tag's value as text: a string as it is, anything else as its JSON."""
    return value if isinstance(value, str) else json.dumps(value)
