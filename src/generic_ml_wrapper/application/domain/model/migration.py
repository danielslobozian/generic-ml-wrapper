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
