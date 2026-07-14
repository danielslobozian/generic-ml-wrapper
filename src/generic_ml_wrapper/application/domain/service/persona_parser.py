# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Pure parsing of a persona file: frontmatter metadata plus the tone body."""

from __future__ import annotations

import re

from generic_ml_wrapper.application.domain.model.persona import Persona

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
_QUOTED_MIN_LEN = 2  # a quoted value is at least the opening and closing quote


def parse_persona(fallback_name: str, text: str) -> Persona:
    """Parse a persona file into its metadata and tone body.

    The optional leading ``---`` frontmatter supplies ``name``/``description``/
    ``greeting`` (simple ``key: value`` lines, values optionally quoted); everything
    after it is the tone body. A file with no frontmatter is all body.

    Args:
        fallback_name: The name to use when frontmatter omits ``name`` (the file stem).
        text: The raw persona-file text.

    Returns:
        The parsed persona.
    """
    match = _FRONTMATTER.match(text)
    if match is None:
        return Persona(name=fallback_name, description="", greeting="", body=text.strip())
    meta = _parse_meta(match.group(1))
    return Persona(
        name=meta.get("name") or fallback_name,
        description=meta.get("description", ""),
        greeting=meta.get("greeting", ""),
        body=match.group(2).strip(),
    )


def _parse_meta(block: str) -> dict[str, str]:
    """Parse ``key: value`` frontmatter lines into a mapping (values unquoted)."""
    meta: dict[str, str] = {}
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = _unquote(value.strip())
    return meta


def _unquote(value: str) -> str:
    """Strip a single pair of matching surrounding quotes, if present."""
    if len(value) >= _QUOTED_MIN_LEN and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value
