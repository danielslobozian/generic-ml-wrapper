# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ListPlugins use case, driven by a fake source."""

from generic_ml_wrapper.application.domain.model.plugin import Plugin
from generic_ml_wrapper.application.port.outbound.plugin_source import PluginSourcePort
from generic_ml_wrapper.application.usecase.list_plugins import ListPluginsUseCase


class _FakePlugins(PluginSourcePort):
    def __init__(self, plugins: list[Plugin]) -> None:
        self._plugins = plugins

    def available(self) -> list[Plugin]:
        return self._plugins

    def resolve_caller(self, reference: str) -> str:
        raise NotImplementedError


def test_lists_the_source_plugins() -> None:
    plugins = [Plugin("cursor-mitm", "MITM proxy")]
    assert ListPluginsUseCase(_FakePlugins(plugins)).execute() == plugins
