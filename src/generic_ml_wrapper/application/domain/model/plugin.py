# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A plugin: a trusted, id-referenced folder holding a caller implementation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plugin:
    """One installed plugin under ``~/.gmlw/plugins/<id>/``.

    Attributes:
        plugin_id: The plugin's id (its folder name), how config references it.
        description: A one-line summary from its ``plugin.toml`` (may be empty).
    """

    plugin_id: str
    description: str
