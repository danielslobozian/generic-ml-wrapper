# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for discovering plugins and resolving id references."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.plugin import Plugin


class PluginError(ValueError):
    """Raised when a ``[callers]`` value names a plugin id that cannot be resolved."""


class PluginSourcePort(ABC):
    """List installed plugins and resolve a caller reference (a plugin id or a spec)."""

    @abstractmethod
    def available(self) -> list[Plugin]:
        """Return the installed plugins, sorted by id (empty when none).

        Returns:
            The plugins found under the plugins directory.
        """

    @abstractmethod
    def resolve_caller(self, reference: str) -> str:
        """Resolve a ``[callers]`` value to a loadable ``"path.py:Class"`` spec.

        A value containing ``":"`` is already a module/path spec and is returned
        unchanged. A bare value is a plugin id: it is resolved through that plugin's
        ``plugin.toml`` manifest to an absolute spec.

        Args:
            reference: The ``[callers]`` value — a plugin id or a caller spec.

        Returns:
            A loadable ``"module:Class"`` / ``"/path.py:Class"`` spec.

        Raises:
            PluginError: If the id names no installed plugin, or its manifest is bad.
        """
