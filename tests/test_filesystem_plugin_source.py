# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem plugin source."""

from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.plugin.filesystem_plugin_source import (
    FilesystemPluginSource,
)
from generic_ml_wrapper.application.port.outbound.plugin_source import PluginError


def _install(root: Path, plugin_id: str, *, manifest: str) -> None:
    folder = root / plugin_id
    folder.mkdir(parents=True)
    (folder / "plugin.toml").write_text(manifest, encoding="utf-8")
    (folder / f"{plugin_id.replace('-', '_')}.py").write_text("", encoding="utf-8")


def test_available_lists_installed_plugins_sorted(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    _install(root, "cursor-mitm", manifest='[plugin]\ndescription = "MITM"\ncaller = "x.py:C"\n')
    _install(root, "acme", manifest='[plugin]\ndescription = "Acme"\ncaller = "y.py:D"\n')
    plugins = FilesystemPluginSource(root).available()
    assert [(p.plugin_id, p.description) for p in plugins] == [
        ("acme", "Acme"),
        ("cursor-mitm", "MITM"),
    ]


def test_available_is_empty_without_a_plugins_dir(tmp_path: Path) -> None:
    assert FilesystemPluginSource(tmp_path / "nope").available() == []


def test_resolve_id_returns_an_absolute_spec(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    _install(root, "cursor-mitm", manifest='[plugin]\ncaller = "cursor_mitm.py:CursorMitmCaller"\n')
    resolved = FilesystemPluginSource(root).resolve_caller("cursor-mitm")
    assert resolved == f"{root / 'cursor-mitm' / 'cursor_mitm.py'}:CursorMitmCaller"


def test_resolve_passes_a_spec_through_unchanged(tmp_path: Path) -> None:
    source = FilesystemPluginSource(tmp_path / "plugins")
    assert source.resolve_caller("/abs/x.py:C") == "/abs/x.py:C"
    assert source.resolve_caller("pkg.mod:Class") == "pkg.mod:Class"


def test_resolve_unknown_id_raises(tmp_path: Path) -> None:
    with pytest.raises(PluginError, match="unknown plugin id"):
        FilesystemPluginSource(tmp_path / "plugins").resolve_caller("ghost")


def test_resolve_bad_manifest_caller_raises(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    _install(root, "broken", manifest='[plugin]\ncaller = "no-colon-here"\n')
    with pytest.raises(PluginError, match="caller must be"):
        FilesystemPluginSource(root).resolve_caller("broken")


def test_resolve_hook_id_returns_an_absolute_spec(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    _install(root, "deployer", manifest='[plugin]\nhook = "deployer.py:SkillsDeployer"\n')
    resolved = FilesystemPluginSource(root).resolve_hook("deployer")
    assert resolved == f"{root / 'deployer' / 'deployer.py'}:SkillsDeployer"


def test_resolve_hook_passes_a_spec_through_unchanged(tmp_path: Path) -> None:
    source = FilesystemPluginSource(tmp_path / "plugins")
    assert source.resolve_hook("pkg.mod:Hook") == "pkg.mod:Hook"


def test_resolve_hook_bad_manifest_raises(tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    _install(root, "broken", manifest='[plugin]\nhook = "no-colon-here"\n')
    with pytest.raises(PluginError, match="hook must be"):
        FilesystemPluginSource(root).resolve_hook("broken")
