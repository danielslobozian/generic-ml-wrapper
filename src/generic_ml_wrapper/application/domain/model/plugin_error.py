# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Raised when a ``[callers]`` value names a plugin id that cannot be resolved."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class PluginError(ValueError):
    """Raised when a ``[callers]`` value names a plugin id that cannot be resolved."""
