# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for writing settings into the TOML config, preserving the rest."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


class ConfigWriterPort(ABC):
    """Merge settings into ``config.toml`` without disturbing the user's other content.

    A round-trip editor: it sets or clears specific ``table.key`` entries while keeping
    every other key, comment, and the file's formatting exactly. This honours the rule
    that a user's input is never lost — a change is merged in, the file is never rewritten
    from scratch.
    """

    @abstractmethod
    def merge(
        self, path: Path, entries: Sequence[tuple[str, str, object | None]]
    ) -> tuple[str, ...]:
        """Apply ``(table, key, value)`` entries to the config, in order.

        A non-``None`` value sets the key (creating the table if absent); a ``None`` value
        clears the key (removing it if present). The file is created if it does not exist.

        Args:
            path: The config file to merge into.
            entries: The ``(table, key, value)`` triples to apply.

        Returns:
            One ``"table.key: old → new"`` line for each entry that replaced or cleared an
            existing value (empty when nothing changed) — so a change is surfaced, never
            silent.
        """
