# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""What the slug migration renamed: raw-named folders to clean slug-folders."""

from __future__ import annotations

from dataclasses import dataclass, field


def _empty_pairs() -> list[tuple[str, str]]:
    """A typed empty-list factory for the (old, new) rename pairs."""
    return []


@dataclass(frozen=True)
class SlugMigrationReport:
    """What the slug migration renamed: existing raw-named folders → clean slug-folders.

    Attributes:
        renamed: ``(old_name, new_slug)`` pairs for every role/environment folder whose
            name was not already a slug and was renamed (in order). Empty on a no-op.
    """

    renamed: list[tuple[str, str]] = field(default_factory=_empty_pairs)

    @property
    def did_anything(self) -> bool:
        """Whether anything was renamed (else the migration was a no-op)."""
        return bool(self.renamed)
