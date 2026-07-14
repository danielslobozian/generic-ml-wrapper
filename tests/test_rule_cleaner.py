# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the pure rule-cleaning service."""

from generic_ml_wrapper.application.domain.service.rule_cleaner import clean_rule

_SECTIONS = ("Origin", "Notes")


def test_frontmatter_is_dropped() -> None:
    raw = "---\nname: r1\nstatus: active\n---\n\n**Rule:** always test."
    assert clean_rule(raw, _SECTIONS) == "**Rule:** always test."


def test_human_only_sections_are_dropped() -> None:
    raw = "**Rule:** always test.\n\n**Origin:** learned on JOB-1.\n\n**Notes:** mine."
    assert clean_rule(raw, _SECTIONS) == "**Rule:** always test."


def test_a_section_stops_at_the_next_rule_title() -> None:
    raw = "**Rule:** one.\n\n**Origin:** note.\n\n# next\n\n**Rule:** two."
    cleaned = clean_rule(raw, _SECTIONS)
    assert "**Origin:**" not in cleaned
    assert "# next" in cleaned
    assert "**Rule:** two." in cleaned


def test_no_sections_only_drops_frontmatter() -> None:
    raw = "---\nname: r\n---\n\n**Rule:** x.\n\n**Origin:** keep me."
    assert clean_rule(raw, ()) == "**Rule:** x.\n\n**Origin:** keep me."


def test_is_idempotent() -> None:
    raw = "---\nname: r\n---\n\n**Rule:** x.\n\n**Origin:** note."
    once = clean_rule(raw, _SECTIONS)
    assert clean_rule(once, _SECTIONS) == once
