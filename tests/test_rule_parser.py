# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the pure rule parser that the Rules browser summarises files through."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.rules import RULE_TEMPLATE
from generic_ml_wrapper.application.domain.service import rule_parser

_RULE = """\
---
name: no-force-push
status: active
---
# no-force-push

**Rule:** Never force-push a shared branch.

**When:** Any push to a branch someone else may have pulled.

**Strength:** hard

**Origin:** the afternoon we lost a morning's commits.
"""


def test_field_reads_a_bold_section_first_line() -> None:
    assert rule_parser.field(_RULE, "Rule") == "Never force-push a shared branch."
    assert rule_parser.field(_RULE, "Strength") == "hard"


def test_field_is_empty_for_an_absent_section() -> None:
    assert rule_parser.field(_RULE, "Signals") == ""


def test_field_collapses_whitespace() -> None:
    assert rule_parser.field("**Rule:**   be    careful.", "Rule") == "be careful."


def test_frontmatter_value_reads_a_key() -> None:
    assert rule_parser.frontmatter_value(_RULE, "status") == "active"
    assert rule_parser.frontmatter_value(_RULE, "name") == "no-force-push"


def test_frontmatter_value_is_empty_without_frontmatter() -> None:
    assert rule_parser.frontmatter_value("**Rule:** x.", "status") == ""


def test_is_draft_reads_the_status_key() -> None:
    assert rule_parser.is_draft(_RULE) is False
    assert rule_parser.is_draft(_RULE.replace("status: active", "status: draft")) is True


def test_is_draft_ignores_the_phrase_in_prose() -> None:
    # The old substring check misread any rule that merely *mentioned* drafting, silently
    # dropping a live rule from every session. Status is frontmatter, so read it there.
    prose = _RULE.replace("the afternoon we lost", "asked while status: draft was on screen")
    assert rule_parser.is_draft(prose) is False


def test_the_seeded_template_is_active_not_draft() -> None:
    # The user demanded the correction, so it applies from the moment it is recorded.
    # `draft` is their later off-switch, not a gate the rule has to pass first.
    assert rule_parser.frontmatter_value(RULE_TEMPLATE, "status") == "active"
    assert rule_parser.is_draft(RULE_TEMPLATE) is False
