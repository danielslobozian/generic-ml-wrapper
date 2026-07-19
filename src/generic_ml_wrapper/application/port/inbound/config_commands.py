# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for viewing and changing gmlw settings (the ``config`` commands)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SettingView:
    """One setting's current value alongside its registry metadata.

    Attributes:
        key: The dotted key (e.g. ``profile.default_role``).
        value: The current effective value (the default when unset).
        default: The schema default.
        type_name: A short type label (``str``/``bool``/``choice``/``str?``).
        choices: The allowed values, or ``None`` when unconstrained.
        description: A one-line description.
    """

    key: str
    value: object
    default: object
    type_name: str
    choices: tuple[str, ...] | None
    description: str


@dataclass(frozen=True)
class SetOutcome:
    """The result of a ``config set``.

    Attributes:
        key: The key that was set.
        old: The value before the change (the effective value, default when it was unset).
        new: The value after the change (``None`` when the key was cleared).
        changed: Whether the write actually changed the stored value.
    """

    key: str
    old: object
    new: object
    changed: bool


class ConfigCommands(ABC):
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
