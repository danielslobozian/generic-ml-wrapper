# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The browsable view of the user's rules: which axes carry rules, and what they say."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RuleAxis(Enum):
    """The axis a rule lives on — the two facets that describe the user.

    ``ENVIRONMENT`` rules are constraints of the place (company, project, tooling);
    ``ROLE`` rules are the user's own preferences about the craft. On conflict the
    environment wins: a constraint is not overridden by a preference.
    """

    ENVIRONMENT = "environment"
    ROLE = "role"


@dataclass(frozen=True)
class RuleSummary:
    """One rule, reduced to what a listing shows.

    Attributes:
        slug: The rule's file stem (``no-force-push`` for ``no-force-push.rule.md``).
        rule: The ``**Rule:**`` line — the instruction itself, the listing's subtitle.
        when: The ``**When:**`` line, or ``""``.
        strength: ``hard`` / ``soft`` as authored, or ``""`` when unstated.
        draft: Whether the user has switched it back to draft, so it is injected into no
            session. Rules are active from creation; this is the off-switch, not a gate.
        path: The absolute file path, so the detail panel can say where it lives.
    """

    slug: str
    rule: str
    when: str = ""
    strength: str = ""
    draft: bool = False
    path: str = ""


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
