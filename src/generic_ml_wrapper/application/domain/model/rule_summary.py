# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""One rule, reduced to what a listing shows."""

from __future__ import annotations

from dataclasses import dataclass


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
