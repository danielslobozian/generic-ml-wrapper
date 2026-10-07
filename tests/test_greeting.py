# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the pure greeting service."""

import pytest

from generic_ml_wrapper.application.domain.model.workspace import Workspace
from generic_ml_wrapper.application.domain.service.greeting import (
    daypart,
    greeting_context,
    render_greeting,
    repo_note,
)


def test_greeting_context_wraps_the_greeting_as_a_renderable_section() -> None:
    section = greeting_context("Good evening, Dan.")
    assert section.startswith("# Greeting")
    assert "Good evening, Dan." in section


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (0, "Good evening"),
        (4, "Good evening"),
        (5, "Good morning"),
        (11, "Good morning"),
        (12, "Good afternoon"),
        (17, "Good afternoon"),
        (18, "Good evening"),
        (23, "Good evening"),
    ],
)
def test_daypart_maps_the_hour(hour: int, expected: str) -> None:
    assert daypart(hour) == expected


def test_repo_note_names_repo_and_branch() -> None:
    ws = Workspace(folder="~/x", repo="gmlw", branch="main", short_sha="abc", dirty=0)
    assert repo_note(ws) == " You're in gmlw (main)."


def test_repo_note_without_branch() -> None:
    ws = Workspace(folder="~/x", repo="gmlw", branch=None, short_sha=None, dirty=0)
    assert repo_note(ws) == " You're in gmlw."


def test_repo_note_empty_outside_a_repo() -> None:
    ws = Workspace(folder="~/x", repo=None, branch=None, short_sha=None, dirty=0)
    assert repo_note(ws) == ""


def test_render_fills_slots_and_collapses_spaces() -> None:
    template = "{daypart}, {name}.{repo_note} How may I help?"
    out = render_greeting(
        template, name="Daniel", daypart="Good evening", repo_note=" You're in gmlw (main)."
    )
    assert out == "Good evening, Daniel. You're in gmlw (main). How may I help?"


def test_render_with_empty_repo_note_leaves_no_double_space() -> None:
    out = render_greeting(
        "{daypart}, {name}.{repo_note} What now?", name="Dan", daypart="Good morning", repo_note=""
    )
    assert out == "Good morning, Dan. What now?"
