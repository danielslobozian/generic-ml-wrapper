# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ``SettingsCatalogPort`` backed by the declared schema and the TOML config file."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.config import settings_registry, toml_config_reader
from generic_ml_wrapper.application.port.outbound.settings_catalog import SettingsCatalogPort

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_wrapper.application.domain.model.setting_row import SettingRow


class TomlSettingsCatalogAdapter(SettingsCatalogPort):
    """Reads the settable surface from the typed registry and the user's ``config.toml``.

    The registry is the single declaration of every scalar key — its type, default,
    allowed values and description — and the reader is the tolerant view of what the file
    currently says. Keeping both behind one port means the ``config`` commands ask one
    collaborator "what can be set, and what is it set to", instead of importing two
    modules and a path.
    """

    def rows(self) -> list[SettingRow]:
        """Return every registered setting's metadata, in declaration order."""
        return settings_registry.registry_rows()

    def current_values(self, path: Path) -> dict[str, object]:
        """Return the current effective value of every registered scalar setting."""
        return toml_config_reader.current_values(path)

    def is_table(self, key: str) -> bool:
        """Whether ``key`` addresses a table of entries rather than a single scalar."""
        return settings_registry.is_table(key)

    def coerce(self, key: str, raw: str) -> object:
        """Convert a typed-in string to the setting's declared type."""
        return settings_registry.coerce(key, raw)

    def parse_entry(self, key: str, raw: str) -> tuple[str, str | None]:
        """Split a table entry's ``name=value`` argument into its parts."""
        return settings_registry.parse_entry(key, raw)
