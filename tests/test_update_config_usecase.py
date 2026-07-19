# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ConfigCommands use case (config list/get/set)."""

from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.config.tomlkit_config_writer import TomlkitConfigWriter
from generic_ml_wrapper.application.usecase.update_config import UpdateConfigUseCase
from generic_ml_wrapper.common import settings_registry


def _commands(config_file: Path) -> UpdateConfigUseCase:
    return UpdateConfigUseCase(writer=TomlkitConfigWriter(), config_file=lambda: config_file)


def test_list_covers_every_registry_key_with_current_values(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[client]\ndefault = "cursor"\n', encoding="utf-8")
    views = {view.key: view for view in _commands(path).list()}
    assert set(views) == set(settings_registry.keys())
    assert views["client.default"].value == "cursor"  # read from file
    assert views["profile.default_role"].value == "default"  # default when unset


def test_get_returns_metadata_and_value(tmp_path: Path) -> None:
    view = _commands(tmp_path / "missing.toml").get("logging.level")
    assert view.value == "warning"
    assert view.choices == ("debug", "info", "warning", "error")


def test_get_unknown_key_raises(tmp_path: Path) -> None:
    with pytest.raises(settings_registry.UnknownSettingError):
        _commands(tmp_path / "missing.toml").get("nope.key")


def test_set_changes_a_value_and_preserves_comments(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '# my config\n[profile]\ndefault_role = "default"  # keep this comment\n',
        encoding="utf-8",
    )
    outcome = _commands(path).set("profile.default_role", "reviewer")
    assert outcome.changed is True
    assert outcome.old == "default"
    assert outcome.new == "reviewer"
    body = path.read_text(encoding="utf-8")
    assert 'default_role = "reviewer"' in body
    assert "# my config" in body  # comments untouched
    assert "# keep this comment" in body


def test_set_creates_a_missing_table(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[init]\nversion = "0.4.0"\n', encoding="utf-8")
    outcome = _commands(path).set("transcript.enabled", "yes")
    assert outcome.new is True
    assert "[transcript]" in path.read_text(encoding="utf-8")


def test_set_rejects_a_value_outside_the_allowed_set(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    with pytest.raises(settings_registry.InvalidSettingValueError):
        _commands(path).set("logging.level", "loud")
    assert not path.exists()  # nothing written on a rejected value


def test_set_unknown_key_raises(tmp_path: Path) -> None:
    with pytest.raises(settings_registry.UnknownSettingError):
        _commands(tmp_path / "config.toml").set("nope.key", "x")


def test_set_clears_an_optional_key(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[companion]\nname = "Dan"\n', encoding="utf-8")
    outcome = _commands(path).set("companion.name", "none")
    assert outcome.new is None
    assert "name" not in path.read_text(encoding="utf-8")


def test_set_reports_a_noop_as_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[logging]\nlevel = "warning"\n', encoding="utf-8")
    outcome = _commands(path).set("logging.level", "warning")
    assert outcome.changed is False
