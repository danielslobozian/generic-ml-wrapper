# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``ConfigWriterPort``: a tomlkit round-trip merge into ``config.toml``."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import tomlkit
from tomlkit.items import Table

from generic_ml_wrapper.application.port.outbound.config_writer import ConfigWriterPort

if TYPE_CHECKING:
    from collections.abc import MutableMapping, Sequence
    from pathlib import Path


class TomlkitConfigWriter(ConfigWriterPort):
    """Merge settings into ``config.toml`` with tomlkit, keeping comments and formatting.

    tomlkit reads and rewrites TOML while preserving the user's keys, comments, and layout
    exactly; stdlib ``tomllib`` can only read. This is the one writer both init (merging a
    legacy config) and ``config set`` (changing one key) share, so a user's file is edited
    in place, never regenerated.
    """

    def merge(
        self, path: Path, entries: Sequence[tuple[str, str, object | None]]
    ) -> tuple[str, ...]:
        """Set or clear each ``(table, key, value)`` entry; return the replaced lines.

        Args:
            path: The config file to merge into (created if absent).
            entries: The ``(table, key, value)`` triples; ``None`` clears the key.

        Returns:
            The ``"table.key: old → new"`` lines for entries that changed an existing value.
        """
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        doc = tomlkit.parse(text)
        # tomlkit's containers are mapping-like but loosely typed; view them as typed
        # mappings so the merge stays fully checked.
        container = cast("MutableMapping[str, object]", doc)
        overwrites: list[str] = []
        for table_name, key, value in entries:
            node = container.get(table_name)
            table = node if isinstance(node, Table) else None
            if value is None:  # clear the key (only if it is currently present)
                overwrites += self._clear(table, table_name, key)
                continue
            if table is None:  # the table is absent (or not a table) — add a fresh one
                table = tomlkit.table()
                container[table_name] = table
            overwrites += self._set(table, table_name, key, value)
        path.write_text(tomlkit.dumps(doc), encoding="utf-8")
        return tuple(overwrites)

    @staticmethod
    def _set(table: Table, table_name: str, key: str, value: object) -> list[str]:
        """Set ``key`` in ``table``; return the overwrite line when it replaced a value."""
        entries = cast("MutableMapping[str, object]", table)
        old = entries.get(key)
        replaced = old is not None and str(old) != str(value)
        line = [f"{table_name}.{key}: {old!s} → {value}"] if replaced else []
        entries[key] = value
        return line

    @staticmethod
    def _clear(table: Table | None, table_name: str, key: str) -> list[str]:
        """Remove ``key`` from ``table`` when present; return the cleared line."""
        if table is None:
            return []
        entries = cast("MutableMapping[str, object]", table)
        old = entries.get(key)
        if old is None:
            return []
        del entries[key]
        return [f"{table_name}.{key}: {old!s} → (unset)"]
