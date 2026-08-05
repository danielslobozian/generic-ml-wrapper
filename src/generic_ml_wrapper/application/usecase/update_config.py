# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ConfigCommandsUseCase use case: list/get/set settings, validated against the registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from generic_ml_wrapper.application.domain.model.unknown_setting_error import UnknownSettingError
from generic_ml_wrapper.application.port.inbound.config_commands import ConfigCommandsUseCase
from generic_ml_wrapper.application.port.inbound.set_outcome import SetOutcome
from generic_ml_wrapper.application.port.inbound.setting_view import SettingView

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from generic_ml_wrapper.application.domain.model.setting_row import SettingRow
    from generic_ml_wrapper.application.port.outbound.config_writer import ConfigWriterPort
    from generic_ml_wrapper.application.port.outbound.settings_catalog import SettingsCatalogPort


class UpdateConfigService(ConfigCommandsUseCase):
    """Render and mutate the settable scalar settings.

    Reads the schema and the current values through :class:`SettingsCatalogPort`. Writes
    go through the shared :class:`ConfigWriterPort`, so a change is merged into the user's
    file, never rewritten.
    """

    def __init__(
        self,
        writer: ConfigWriterPort,
        config_file: Callable[[], Path],
        settings: SettingsCatalogPort,
    ) -> None:
        """Wire the use case to its writer, the config-file locator, and the catalogue.

        Args:
            writer: Persists a changed key, preserving the rest of the file.
            config_file: Resolves the config file path (indirection for tests).
            settings: What may be set, and what it is currently set to.
        """
        self._writer = writer
        self._config_file = config_file
        self._settings = settings

    def list(self) -> list[SettingView]:
        """Return every setting with its current value and metadata, in registry order."""
        current = self._settings.current_values(self._config_file())
        return [
            SettingView(
                key=row.key,
                value=current[row.key],
                default=row.default,
                type_name=row.type_name,
                choices=row.choices,
                description=row.description,
            )
            for row in self._settings.rows()
        ]

    def get(self, key: str) -> SettingView:
        """Return one setting (raises :class:`UnknownSettingError` for an unknown key)."""
        row = self._row(key)
        current = self._settings.current_values(self._config_file())
        return SettingView(
            key=row.key,
            value=current[row.key],
            default=row.default,
            type_name=row.type_name,
            choices=row.choices,
            description=row.description,
        )

    def set(self, key: str, raw: str) -> SetOutcome:
        """Validate ``raw`` against the registry and persist it, surfacing the change."""
        if self._settings.is_table(key):  # raises Unknown before any write
            return self._set_entry(key, raw)
        coerced = self._settings.coerce(key, raw)  # raises Unknown/Invalid before any write
        path = self._config_file()
        old = self._settings.current_values(path)[key]
        table, field = key.split(".", 1)
        # The writer only reports *replaced* existing keys, so it can't tell a first-time
        # set from a no-op; compare effective values to decide whether anything changed.
        self._writer.merge(path, [(table, field, coerced)])
        return SetOutcome(key=key, old=old, new=coerced, changed=old != coerced)

    def _set_entry(self, key: str, raw: str) -> SetOutcome:
        """Set or clear one entry of a table setting, keeping the rest of the table.

        The table is read, the single entry applied, and the whole table written back —
        so ``config set client.args codex="…"`` never drops the claude entry beside it.
        An empty value (``claude=``) removes that entry rather than storing "".
        """
        name, value = self._settings.parse_entry(key, raw)
        path = self._config_file()
        current = self._settings.current_values(path)[key]
        old: dict[str, str] = cast("dict[str, str]", current) if isinstance(current, dict) else {}
        entries = dict(old)
        if value is None:
            entries.pop(name, None)
        else:
            entries[name] = value
        table, field = key.split(".", 1)
        self._writer.merge(path, [(table, field, entries)])
        return SetOutcome(key=key, old=old, new=entries, changed=old != entries)

    def _row(self, key: str) -> SettingRow:
        """Return the registry row for ``key``, or raise :class:`UnknownSettingError`."""
        for row in self._settings.rows():
            if row.key == key:
                return row
        raise UnknownSettingError(key)
