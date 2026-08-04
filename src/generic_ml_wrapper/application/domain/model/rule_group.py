# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The rules held by one environment or role."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.rule_axis import RuleAxis

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.rule_summary import RuleSummary


@dataclass(frozen=True)
class RuleGroup:
    """The rules held by one environment or role.

    Only groups that actually hold rules are listed, so an axis the user has never
    written to never appears as an empty branch to walk into.

    Attributes:
        axis: Which axis this group sits on.
        slug: The environment or role slug (``work``, ``software-engineer``).
        label: The human label from the folder's ``.about.toml``, falling back to the slug.
        rules: The group's rules, drafts included, sorted by slug.
    """

    axis: RuleAxis
    slug: str
    label: str
    rules: tuple[RuleSummary, ...] = ()

    @property
    def draft_count(self) -> int:
        """How many of the group's rules the user has switched off."""
        return sum(1 for rule in self.rules if rule.draft)
