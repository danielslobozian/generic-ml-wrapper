# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when a dotted key names no registered setting."""

from __future__ import annotations


class UnknownSettingError(KeyError):
    """Raised when a dotted key is not a registered setting."""

    def __init__(self, key: str) -> None:
        """Record the offending key.

        Args:
            key: The unknown dotted key.
        """
        self.key = key
        super().__init__(key)

    def __str__(self) -> str:
        """Render a plain, un-repr'd message (KeyError would quote it)."""
        return f"unknown setting {self.key!r}"
