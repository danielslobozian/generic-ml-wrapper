# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListPlugins use case: report the installed plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_plugins import ListPlugins

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.plugin import Plugin
    from generic_ml_wrapper.application.port.outbound.plugin_source import PluginSourcePort


class ListPluginsUseCase(ListPlugins):
    """Return the installed plugins from the plugin source."""

    def __init__(self, plugins: PluginSourcePort) -> None:
        """Wire the use case to its plugin source.

        Args:
            plugins: The source that discovers installed plugins.
        """
        self._plugins = plugins

    def execute(self) -> list[Plugin]:
        """Return the installed plugins, sorted by id.

        Returns:
            The plugins (empty if none are installed).
        """
        return self._plugins.available()
