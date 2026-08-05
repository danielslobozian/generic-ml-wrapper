# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ApplicationSettingsUseCase use case: answer the delivery layer's questions about config."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.application_settings import (
    ApplicationSettingsUseCase,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.companion_settings import CompanionSettings
    from generic_ml_wrapper.application.port.outbound.runtime_config import RuntimeConfigPort


class ReadApplicationSettingsService(ApplicationSettingsUseCase):
    """Answer from the configured runtime settings, without exposing where they live."""

    def __init__(self, config: RuntimeConfigPort) -> None:
        """Wire the use case to the configured settings.

        Args:
            config: Where the user's answers are read from.
        """
        self._config = config

    def setup_needed(self) -> bool:
        """Whether first-time setup has never run.

        Returns:
            ``True`` when nothing has recorded that setup completed.
        """
        return self._config.initialised_version() is None

    def resolve_client(self, explicit: str | None) -> str:
        """Return the client to wrap: the explicit choice, else the configured default."""
        return explicit if explicit else self._config.default_client()

    def companion(self) -> CompanionSettings:
        """Return the companion settings, for greeting and signing off."""
        return self._config.companion()

    def hints_enabled(self) -> bool:
        """Whether one-time tips may be shown."""
        return self._config.hints_enabled()
