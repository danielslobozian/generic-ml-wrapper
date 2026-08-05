# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The result of persisting an init pass, for the caller to narrate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class InitPersist:
    """The result of persisting an init pass, for the caller to narrate.

    Attributes:
        fresh: ``True`` when a brand-new config was written, ``False`` when the answers
            were merged into a pre-existing (legacy) config.
        overwrites: Human-readable ``table.key: old → new`` lines for each existing
            setting the merge replaced with a freshly chosen value (empty on a fresh
            install, or when the merge only added new keys). Surfaced so a changed
            setting is never dropped silently.
    """

    fresh: bool
    overwrites: tuple[str, ...] = ()
