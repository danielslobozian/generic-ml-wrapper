# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The report of a one-shot layout migration, for the caller to surface."""

from __future__ import annotations

from dataclasses import dataclass, field


def _empty() -> list[str]:
    """A typed empty-list factory (keeps the default fields fully typed)."""
    return []


@dataclass(frozen=True)
class MigrationReport:
    """What a layout migration relocated, and what it left in place.

    Attributes:
        environment: The environment the old place-specific context was wrapped into.
        moved: The entry names relocated into ``environments/<environment>/`` (in order).
        skipped: The entry names left in ``profile/company/`` because a same-named entry
            already existed at the target — never overwritten, always surfaced.
    """

    environment: str
    moved: list[str] = field(default_factory=_empty)
    skipped: list[str] = field(default_factory=_empty)

    @property
    def did_anything(self) -> bool:
        """Whether the migration relocated or skipped anything (else it was a no-op)."""
        return bool(self.moved or self.skipped)


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


def _empty_reasons() -> list[tuple[str, str]]:
    """A typed empty-list factory for the (name, reason) pairs."""
    return []


@dataclass(frozen=True)
class LegacyMigrationReport:
    """What the one-time move from the old ``workflows/`` folder to attachments did.

    Attributes:
        imported: ``name@version`` for each folder imported as an attachment (in order).
        skipped: ``(name, reason)`` for each folder left out, with the catalogue key of why.
        config_rewritten: Whether ``config.toml`` had old keys renamed.
        folder: The old folder, left in place for the user to delete; empty when absent.
    """

    imported: list[str] = field(default_factory=_empty)
    skipped: list[tuple[str, str]] = field(default_factory=_empty_reasons)
    config_rewritten: bool = False
    folder: str = ""

    @property
    def did_anything(self) -> bool:
        """Whether the migration imported, skipped or rewrote anything."""
        return bool(self.imported or self.skipped or self.config_rewritten)
