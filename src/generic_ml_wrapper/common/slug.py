# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Turn a free-text label into a filesystem- and config-safe slug.

Role and environment answers become folder names *and* config values, so a typed phrase
(often with spaces, capitals, and — in French — accents) must collapse to a stable,
lowercase, ASCII, kebab-case token. The label the user actually typed is preserved
elsewhere (the folder's ``.about.toml``); this module only derives the technical id.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_MAX_LEN = 40


def slugify(text: str, max_len: int = _MAX_LEN) -> str:
    """Return a kebab-case ASCII slug for ``text`` (accents stripped), possibly empty.

    NFKD-normalises and drops non-ASCII (``é`` -> ``e``), lowercases, replaces every run
    of non-alphanumeric characters with a single dash, strips edge dashes, and trims to
    ``max_len`` on a dash (word) boundary where one exists. Returns ``""`` when nothing
    slug-worthy remains (e.g. an all-symbol input) — callers supply their own fallback.

    Args:
        text: The free-text label to reduce.
        max_len: The maximum slug length; the result is trimmed on a word boundary.

    Returns:
        The slug, or ``""`` when ``text`` has no alphanumeric content.
    """
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if len(slug) <= max_len:
        return slug
    cut = slug[:max_len]
    head = cut.rsplit("-", 1)[0]  # prefer a whole-word boundary over a mid-word chop
    return (head or cut).strip("-")


def unique_slug(base: str, exists: Callable[[str], bool]) -> str:
    """Return ``base``, or the first free ``base-2`` / ``base-3`` / … suffix.

    Args:
        base: An already-slugified, non-empty candidate.
        exists: Reports whether a candidate is already taken (e.g. a folder is present
            with a different description).

    Returns:
        ``base`` when free, else ``base-N`` for the smallest ``N >= 2`` that is not taken.
    """
    if not exists(base):
        return base
    n = 2
    while exists(f"{base}-{n}"):
        n += 1
    return f"{base}-{n}"
