# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the learned-notebook invariants."""

from generic_ml_wrapper.application.domain.model import learned


def test_notebook_template_carries_both_headings() -> None:
    assert learned.POSITIVE_HEADING in learned.NOTEBOOK_TEMPLATE
    assert learned.NEGATIVE_HEADING in learned.NOTEBOOK_TEMPLATE


def test_directive_points_at_the_notebook_and_both_sections() -> None:
    assert "~/.gmlw/profile/me/learned.md" in learned.CAPTURE_DIRECTIVE
    assert learned.POSITIVE_HEADING in learned.CAPTURE_DIRECTIVE
    assert learned.NEGATIVE_HEADING in learned.CAPTURE_DIRECTIVE


def test_directive_makes_negatives_first_class() -> None:
    assert "as valuable as the positives" in learned.CAPTURE_DIRECTIVE


def test_directive_excludes_one_offs_secrets_and_assistant_suggestions() -> None:
    # the field's guardrails: durable facts about the user only
    for guard in ("one-off task details", "secrets", "your own suggestions"):
        assert guard in learned.CAPTURE_DIRECTIVE
