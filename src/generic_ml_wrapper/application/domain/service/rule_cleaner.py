# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Pure rule cleaning: drop bookkeeping and human-only notes before the model sees it."""

from __future__ import annotations

import re
from collections.abc import Sequence

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_BLANKS = re.compile(r"\n{3,}")


def clean_rule(text: str, sections: Sequence[str]) -> str:
    """Strip a rule's frontmatter and any human-only sections, losslessly for the model.

    Removes the leading YAML frontmatter (bookkeeping such as name/status) and each
    ``**Name:**`` section listed in ``sections`` (running until the next ``**Header:**``
    marker, a markdown ``# `` heading, or end of text). Blank runs are collapsed. The
    ``# `` stop is load-bearing: without it a trailing block would swallow the next
    rule's title. Idempotent.

    Args:
        text: The raw rule text.
        sections: Bold-header section names to drop (case-sensitive on the name).

    Returns:
        The cleaned rule text.
    """
    text = _FRONTMATTER.sub("", text, count=1)
    if sections:
        names = "|".join(re.escape(name) for name in sections)
        stop = r"(?:^\*\*[^*:\n]+:\*\*|^#\s)"
        text = re.compile(rf"(?ms)^\*\*(?:{names}):\*\*.*?(?={stop}|\Z)").sub("", text)
    return _BLANKS.sub("\n\n", text).strip()
