# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ``RuntimeConfigPort`` backed by the user's ``config.toml``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.config import toml_config_reader
from generic_ml_wrapper.application.port.outbound.runtime_config import RuntimeConfigPort

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.companion_settings import CompanionSettings


class TomlRuntimeConfigAdapter(RuntimeConfigPort):
    """Read the run-shaping settings from the TOML config file, tolerantly.

    Every answer falls back to a sane default when the file is absent or malformed: a
    broken config must not make the tool that repairs it unusable.
    """

    def initialised_version(self) -> str | None:
        """Return the version that ran first-time setup, or ``None`` when it never has."""
        return toml_config_reader.init_version()

    def default_client(self) -> str:
        """Return the client id to wrap when the caller names none."""
        return toml_config_reader.default_client()

    def companion(self) -> CompanionSettings:
        """Return the companion settings; invisible until a persona is chosen."""
        return toml_config_reader.companion()

    def hints_enabled(self) -> bool:
        """Whether one-time tips may be shown."""
        return toml_config_reader.hints_show()
