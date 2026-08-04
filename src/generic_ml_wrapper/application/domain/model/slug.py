# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The Slug: a free-text label reduced to a filesystem- and config-safe identifier.

Role and environment answers become folder names *and* config values, so a typed phrase
(often with spaces, capitals, and — in French — accents) must collapse to a stable,
lowercase, ASCII, kebab-case token. The label the user actually typed is preserved
elsewhere (the folder's ``.about.toml``); this type only derives the technical id.

It is a domain type rather than a text utility because "what may name a thing here" is
a rule of this application, not a general-purpose string operation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_MAX_LEN = 40


@dataclass(frozen=True)
class Slug:
    """A derived identifier, possibly empty when the label had nothing slug-worthy."""

    value: str

    @classmethod
    def of(cls, text: str, max_len: int = _MAX_LEN) -> Slug:
        """Return the kebab-case ASCII slug for ``text`` (accents stripped), possibly empty.

        NFKD-normalises and drops non-ASCII (``é`` -> ``e``), lowercases, replaces every
        run of non-alphanumeric characters with a single dash, strips edge dashes, and
        trims to ``max_len`` on a dash (word) boundary where one exists. Yields an empty
        slug when nothing slug-worthy remains (e.g. an all-symbol input) — callers supply
        their own fallback.

        Args:
            text: The free-text label to reduce.
            max_len: The maximum slug length; the result is trimmed on a word boundary.

        Returns:
            The slug, empty when ``text`` has no alphanumeric content.
        """
        ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
        if len(slug) <= max_len:
            return cls(slug)
        cut = slug[:max_len]
        head = cut.rsplit("-", 1)[0]  # prefer a whole-word boundary over a mid-word chop
        return cls((head or cut).strip("-"))

    def unique_among(self, taken: Callable[[str], bool]) -> Slug:
        """Return this slug, or the first free ``-2`` / ``-3`` / … suffixed variant.

        Args:
            taken: Reports whether a candidate is already in use (e.g. a folder is
                present with a different description).

        Returns:
            This slug when free, else the smallest ``-N`` variant (``N >= 2``) that is not.
        """
        if not taken(self.value):
            return self
        n = 2
        while taken(f"{self.value}-{n}"):
            n += 1
        return Slug(f"{self.value}-{n}")

    def __str__(self) -> str:
        """Return the slug text, so a slug drops straight into a path or a config value."""
        return self.value
