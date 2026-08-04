# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Pure parsing of a rule file into its browsable summary.

The compile path only ever *strips* a rule (see :mod:`rule_cleaner`); browsing needs the
opposite — read the bookkeeping rather than remove it, so a listing can say whether a rule
is live. Kept pure and free of the filesystem so it tests against fixture strings.
"""

from __future__ import annotations

import re

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
# A "**Name:** value" section header and its first line of prose.
_FIELD = re.compile(r"(?m)^\*\*(?P<name>[^*:\n]+):\*\*[ \t]*(?P<value>.*)$")
_KEY = re.compile(r"(?m)^(?P<key>[A-Za-z_][\w-]*)\s*:\s*(?P<value>.*)$")
_SPACES = re.compile(r"\s+")


class RuleParser:
    """Reads a rule file's bookkeeping and its named fields."""

    def frontmatter_value(self, text: str, key: str) -> str:
        """Return a frontmatter key's value, or ``""`` when absent.

        Args:
            text: The raw rule text.
            key: The frontmatter key to read (e.g. ``"status"``).

        Returns:
            The value with surrounding whitespace removed, or ``""``.
        """
        block = _FRONTMATTER.match(text)
        if block is None:
            return ""
        for line in _KEY.finditer(block.group(1)):
            if line.group("key") == key:
                return line.group("value").strip()
        return ""

    def field(self, text: str, name: str) -> str:
        """Return a ``**Name:**`` field's first line, collapsed to a single space.

        Only the first line is taken: a listing needs a one-liner, and the full body is
        available by opening the file. A field that continues onto later lines is therefore
        truncated at the newline rather than folded in.

        Args:
            text: The raw rule text.
            name: The field name, without asterisks or colon (e.g. ``"Rule"``).

        Returns:
            The field's first line, or ``""`` when the field is absent or empty.
        """
        for match in _FIELD.finditer(text):
            if match.group("name") == name:
                return _SPACES.sub(" ", match.group("value")).strip()
        return ""

    def is_draft(self, text: str) -> bool:
        """Whether a rule has been switched off, and so is *not* injected into any session.

        A rule is active from creation; ``status: draft`` is the user's own off-switch for
        retiring one without deleting it. Reads the ``status`` frontmatter key rather than
        searching the whole file for the phrase, so a rule that merely *mentions* drafting in
        its prose is not misread.

        Args:
            text: The raw rule text.

        Returns:
            ``True`` when the rule has been set back to draft.
        """
        return self.frontmatter_value(text, "status").casefold() == "draft"
