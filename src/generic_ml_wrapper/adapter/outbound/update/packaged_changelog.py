# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``ReleaseNotesPort`` reading the CHANGELOG.md that ships in the package."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.release_notes import ReleaseNotesPort

if TYPE_CHECKING:
    from collections.abc import Sequence
    from importlib.resources.abc import Traversable


def _candidates() -> tuple[Traversable, ...]:
    """The wheel's copy first, then the repository's own for a source checkout.

    The build copies the repository's ``CHANGELOG.md`` into ``resources/`` (see
    ``pyproject.toml``); an editable or unbuilt checkout has no such copy, but runs from
    ``src/`` inside the repository, whose root holds the file itself.
    """
    packaged = resources.files("generic_ml_wrapper").joinpath("resources", "CHANGELOG.md")
    checkout = Path(__file__).resolve().parents[5] / "CHANGELOG.md"
    return packaged, checkout


class PackagedChangelog(ReleaseNotesPort):
    """Read the first of the changelog's places that holds it."""

    def __init__(self, candidates: Sequence[Traversable] | None = None) -> None:
        """Bind to where the changelog may be.

        Args:
            candidates: Those places, in order; the packaged copy, then the checkout's.
        """
        self._candidates = _candidates() if candidates is None else tuple(candidates)

    def read(self) -> str | None:
        """Return the first changelog found, or ``None``; an unreadable one is skipped."""
        for candidate in self._candidates:
            try:
                if candidate.is_file():
                    return candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
        return None
