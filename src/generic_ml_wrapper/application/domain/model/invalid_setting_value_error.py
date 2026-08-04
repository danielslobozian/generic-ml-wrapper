# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when a value is rejected by the setting it was written for."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class InvalidSettingValueError(DomainError, ValueError):
    """Raised when a value is not valid for a setting (bad type or not an allowed value)."""

    def __init__(self, key: str, value: str, choices: tuple[str, ...] | None) -> None:
        """Record the rejected value and any allowed set.

        Args:
            key: The dotted key being set.
            value: The rejected raw value.
            choices: The allowed values, or ``None`` when the constraint is a type.
        """
        self.key = key
        self.value = value
        self.choices = choices
        if choices:
            super().__init__(
                "error.setting.invalid_choice", key=key, value=value, choices=", ".join(choices)
            )
        else:
            super().__init__("error.setting.invalid_value", key=key, value=value)
