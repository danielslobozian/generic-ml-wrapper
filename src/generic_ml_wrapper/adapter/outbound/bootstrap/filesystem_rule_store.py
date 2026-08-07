# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The rules stored inside a role or environment folder, as ``rules/*.rule.md``.

The storage shape is this file's business and nobody else's: a folder holding one markdown
file per rule, the file stem as the rule's code. A role and an environment store their
rules identically, so both repository adapters read them through here rather than each
carrying its own copy of the layout.

Reading is for *browsing*, so drafts are included and flagged rather than skipped: the
question a listing answers is "what is live, and what am I still sitting on?".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.rule import Rule
from generic_ml_wrapper.application.domain.service.rule_parser import RuleParser

if TYPE_CHECKING:
    from pathlib import Path

_RULE_GLOB = "*.rule.md"
_SUFFIX = ".rule.md"


class FilesystemRuleStore:
    """Read the rules held in a folder, one markdown file per rule."""

    def find_all(self, folder: Path) -> tuple[Rule, ...]:
        """Read every rule in a folder, sorted by file name.

        Best-effort: an unreadable file is skipped rather than raised, so browsing never
        fails on one malformed rule. An absent folder simply holds no rules.

        Args:
            folder: The ``rules/`` folder inside a role or environment.

        Returns:
            The rules found, drafts included and flagged.
        """
        if not folder.is_dir():
            return ()
        parser = RuleParser()
        found: list[Rule] = []
        for path in sorted(folder.glob(_RULE_GLOB)):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue  # one unreadable rule never breaks the listing
            found.append(
                Rule(
                    code=path.name[: -len(_SUFFIX)],
                    rule=parser.field(text, "Rule"),
                    when=parser.field(text, "When"),
                    strength=parser.field(text, "Strength"),
                    draft=parser.is_draft(text),
                    path=str(path),
                )
            )
        return tuple(found)
