# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for viewing and changing gmlw settings (the ``config`` commands)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.set_outcome import SetOutcome
from generic_ml_wrapper.application.port.inbound.setting_view import SettingView


class ConfigCommandsUseCase(ABC):
    """View and change the settable scalar settings, validated against the registry."""

    @abstractmethod
    def list(self) -> list[SettingView]:
        """Return every setting with its current value and metadata, in registry order."""

    @abstractmethod
    def get(self, key: str) -> SettingView:
        """Return one setting.

        Args:
            key: The dotted key to read.

        Returns:
            The setting's view.

        Raises:
            UnknownSettingError: If the key is not a registered setting.
        """

    @abstractmethod
    def set(self, key: str, raw: str) -> SetOutcome:
        """Validate and persist a new value for one setting.

        Args:
            key: The dotted key to change.
            raw: The new value as typed on the command line.

        Returns:
            The outcome, carrying old and new values so the change is surfaced.

        Raises:
            UnknownSettingError: If the key is not a registered setting.
            InvalidSettingValueError: If the value is not valid for the key.
        """
