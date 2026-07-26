# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the session snapshot block that opens every compiled context."""

from __future__ import annotations

import json
import re

from generic_ml_wrapper.application.domain.model.session_snapshot import SessionSnapshot

_FENCE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def _payload(rendered: str) -> dict[str, str]:
    block = _FENCE.search(rendered)
    assert block is not None
    return json.loads(block.group(1))


def test_render_carries_every_selection() -> None:
    snapshot = SessionSnapshot(
        user_name="Daniel",
        user_prefered_language="fr",
        user_environment="work",
        user_role="software-engineer",
        ai_persona="butler",
        job_name="nightly-etl",
    )
    assert _payload(snapshot.render()) == {
        "user_name": "Daniel",
        "user_prefered_language": "fr",
        "user_environment": "work",
        "user_role": "software-engineer",
        "ai_persona": "butler",
        "job_name": "nightly-etl",
    }


def test_unset_fields_render_as_empty_not_dropped() -> None:
    # A stable six-key shape means a client never has to handle a missing field.
    assert set(_payload(SessionSnapshot().render())) == {
        "user_name",
        "user_prefered_language",
        "user_environment",
        "user_role",
        "ai_persona",
        "job_name",
    }
    assert set(_payload(SessionSnapshot().render()).values()) == {""}


def test_render_is_valid_json_under_a_header() -> None:
    rendered = SessionSnapshot(user_name="Daniel").render()
    assert rendered.startswith("## This session")
    assert _payload(rendered)["user_name"] == "Daniel"


def test_non_ascii_values_are_not_escaped() -> None:
    # A French name must read as itself in the context, not as \\uXXXX noise.
    rendered = SessionSnapshot(user_name="Zoé", user_prefered_language="fr").render()
    assert "Zoé" in rendered
