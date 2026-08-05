# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ConfigCommandsUseCase use case (config list/get/set)."""

from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.config import settings_registry
from generic_ml_wrapper.adapter.outbound.config import toml_config_reader as config
from generic_ml_wrapper.adapter.outbound.config.toml_settings_catalog import (
    TomlSettingsCatalogAdapter,
)
from generic_ml_wrapper.adapter.outbound.config.tomlkit_config_writer import (
    TomlkitConfigWriterAdapter,
)
from generic_ml_wrapper.application.usecase.update_config import UpdateConfigService


def _commands(config_file: Path) -> UpdateConfigService:
    return UpdateConfigService(
        writer=TomlkitConfigWriterAdapter(lambda: config_file),
        settings=TomlSettingsCatalogAdapter(lambda: config_file),
    )


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


# ── table settings: one entry at a time, merged ──
def test_setting_a_table_entry_writes_it(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[client]\ndefault = "claude"\n', encoding="utf-8")
    outcome = _commands(path).set("client.args", "claude=--yolo")
    assert outcome.new == {"claude": "--yolo"}
    assert outcome.changed is True
    assert config.client_args(path) == {"claude": "--yolo"}


def test_setting_one_entry_keeps_the_others(tmp_path: Path) -> None:
    # The whole reason the table is read-modify-written rather than replaced: configuring
    # codex must not silently drop the claude flags sitting beside it.
    path = tmp_path / "config.toml"
    path.write_text('[client.args]\nclaude = "--yolo"\n', encoding="utf-8")
    _commands(path).set("client.args", "codex=--profile work")
    assert config.client_args(path) == {"claude": "--yolo", "codex": "--profile work"}


def test_clearing_one_entry_leaves_the_rest(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[client.args]\nclaude = "--yolo"\ncodex = "--profile work"\n', encoding="utf-8"
    )
    outcome = _commands(path).set("client.args", "claude=")
    assert outcome.new == {"codex": "--profile work"}
    assert config.client_args(path) == {"codex": "--profile work"}


def test_setting_a_table_entry_preserves_the_rest_of_the_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '# a comment the user cares about\n[client]\ndefault = "cursor"\n', encoding="utf-8"
    )
    _commands(path).set("client.args", "cursor=--yolo")
    text = path.read_text(encoding="utf-8")
    assert "# a comment the user cares about" in text
    assert config.default_client(path) == "cursor"


def test_re_setting_the_same_entry_reports_no_change(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[client.args]\nclaude = "--yolo"\n', encoding="utf-8")
    assert _commands(path).set("client.args", "claude=--yolo").changed is False


def test_a_table_entry_appears_in_list_with_its_current_value(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[client.args]\nclaude = "--yolo"\n', encoding="utf-8")
    views = {view.key: view for view in _commands(path).list()}
    assert views["client.args"].value == {"claude": "--yolo"}
    assert views["client.args"].type_name == "table"
