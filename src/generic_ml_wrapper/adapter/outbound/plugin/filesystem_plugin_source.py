# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``PluginSourcePort``: plugins under ``~/.gmlw/plugins/<id>/``."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, cast

from generic_ml_wrapper.application.domain.model.plugin import Plugin
from generic_ml_wrapper.application.port.outbound.plugin_source import (
    PluginError,
    PluginSourcePort,
)

if TYPE_CHECKING:
    from pathlib import Path

_MANIFEST = "plugin.toml"


class FilesystemPluginSource(PluginSourcePort):
    """Discover plugins by their ``plugin.toml`` manifest and resolve id references.

    A plugin is a folder ``<root>/<id>/`` with a ``plugin.toml``::

        [plugin]
        description = "Cursor via a metering TLS-MITM proxy"
        caller = "cursor_mitm.py:CursorMitmCaller"   # relative to this folder

    so a ``[callers]`` override can say ``cursor = "cursor-mitm"`` (an id) instead of
    an absolute ``"/path/to/cursor_mitm.py:CursorMitmCaller"`` spec.
    """

    def __init__(self, root: Path) -> None:
        """Bind the source to the plugins directory.

        Args:
            root: The ``~/.gmlw/plugins`` directory.
        """
        self._root = root

    def available(self) -> list[Plugin]:
        """Return the installed plugins (those with a manifest), sorted by id."""
        if not self._root.is_dir():
            return []
        plugins: list[Plugin] = []
        for child in sorted(self._root.iterdir()):
            if not (child / _MANIFEST).is_file():
                continue
            manifest = self._manifest_or_empty(child.name)
            description = manifest.get("description")
            plugins.append(Plugin(child.name, description if isinstance(description, str) else ""))
        return plugins

    def resolve_caller(self, reference: str) -> str:
        """Resolve a caller reference: a spec passes through, an id via its manifest."""
        if ":" in reference:  # already a module/path spec
            return reference
        manifest = self._manifest(reference)
        caller = manifest.get("caller")
        if not isinstance(caller, str) or ":" not in caller:
            message = f'plugin {reference!r}: [plugin] caller must be "file.py:Class"'
            raise PluginError(message)
        relative, _, class_name = caller.partition(":")
        path = (self._root / reference / relative).resolve()
        return f"{path}:{class_name}"

    def _manifest(self, plugin_id: str) -> dict[str, object]:
        """Read the ``[plugin]`` table for an id, raising ``PluginError`` on any problem."""
        path = self._root / plugin_id / _MANIFEST
        if not path.is_file():
            message = f"unknown plugin id {plugin_id!r} (no {path})"
            raise PluginError(message)
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as error:
            message = f"plugin {plugin_id!r}: cannot read manifest ({error})"
            raise PluginError(message) from error
        plugin = data.get("plugin")
        return cast("dict[str, object]", plugin) if isinstance(plugin, dict) else {}

    def _manifest_or_empty(self, plugin_id: str) -> dict[str, object]:
        """Like :meth:`_manifest` but return ``{}`` instead of raising (for listing)."""
        try:
            return self._manifest(plugin_id)
        except PluginError:
            return {}
