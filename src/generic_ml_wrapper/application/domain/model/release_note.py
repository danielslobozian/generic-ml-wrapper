# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""One release's entry in the changelog."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseNote:
    """What one release changed, as the changelog tells it.

    Attributes:
        version: The release, ``"0.12.1"``; ``"Unreleased"`` for what is not out yet.
        date: The release date as written (``"2026-10-11"``), or ``None`` without one.
        body: The entry's Markdown, its ``### Added`` / ``### Fixed`` sections included.
    """

    version: str
    date: str | None
    body: str
