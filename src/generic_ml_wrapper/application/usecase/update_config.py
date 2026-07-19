# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ConfigCommands use case: list/get/set settings, validated against the registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.config_commands import (
    ConfigCommands,
    SetOutcome,
    SettingView,
)
from generic_ml_wrapper.common import config, settings_registry

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from generic_ml_wrapper.application.port.outbound.config_writer import ConfigWriterPort


class UpdateConfigUseCase(ConfigCommands):
    """Render and mutate the settable scalar settings.

    Reads current values through :mod:`config` (authoritative, tolerant) and metadata
    through :mod:`settings_registry` (the schema). Writes go through the shared
    :class:`ConfigWriterPort`, so a change is merged into the user's file, never rewritten.
    """

    def __init__(self, writer: ConfigWriterPort, config_file: Callable[[], Path]) -> None:
        """Wire the use case to its writer and the config-file locator.

        Args:
            writer: Persists a changed key, preserving the rest of the file.
            config_file: Resolves the config file path (indirection for tests).
        """
        self._writer = writer
        self._config_file = config_file

    def list(self) -> list[SettingView]:
        """Return every setting with its current value and metadata, in registry order."""
        current = config.current_values(self._config_file())
        return [
            SettingView(
                key=row.key,
                value=current[row.key],
                default=row.default,
                type_name=row.type_name,
                choices=row.choices,
                description=row.description,
            )
            for row in settings_registry.registry_rows()
        ]

    def get(self, key: str) -> SettingView:
        """Return one setting (raises :class:`UnknownSettingError` for an unknown key)."""
        row = self._row(key)
        current = config.current_values(self._config_file())
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
        coerced = settings_registry.coerce(key, raw)  # raises Unknown/Invalid before any write
        path = self._config_file()
        old = config.current_values(path)[key]
        table, field = key.split(".", 1)
        # The writer only reports *replaced* existing keys, so it can't tell a first-time
        # set from a no-op; compare effective values to decide whether anything changed.
        self._writer.merge(path, [(table, field, coerced)])
        return SetOutcome(key=key, old=old, new=coerced, changed=old != coerced)

    @staticmethod
    def _row(key: str) -> settings_registry.SettingRow:
        """Return the registry row for ``key``, or raise :class:`UnknownSettingError`."""
        for row in settings_registry.registry_rows():
            if row.key == key:
                return row
        raise settings_registry.UnknownSettingError(key)
