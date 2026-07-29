# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the config registry (the typed source of truth for settable keys)."""

from pathlib import Path

import pytest

from generic_ml_wrapper.common import config, settings_registry


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_registry_covers_the_settable_scalar_keys() -> None:
    assert set(settings_registry.keys()) == {
        "client.default",
        "client.args",
        "language.code",
        "profile.default_role",
        "profile.default_environment",
        "logging.level",
        "logging.to_file",
        "logging.max_bytes",
        "logging.backup_count",
        "companion.persona",
        "companion.name",
        "transcript.enabled",
        "transcript.root",
        "compress.adapter",
        "compress.model",
        "compress.effort",
        "hints.show",
        "ambient.capability_card",
    }


def test_rows_carry_type_default_choices_and_description() -> None:
    rows = {row.key: row for row in settings_registry.registry_rows()}
    assert rows["client.default"].default == "claude"
    assert rows["client.default"].description  # non-empty
    level = rows["logging.level"]
    assert level.type_name == "choice"
    assert level.choices == ("debug", "info", "warning", "error")
    assert rows["transcript.enabled"].type_name == "bool"
    assert rows["companion.name"].type_name == "str?"


def test_coerce_bool_accepts_truthy_and_falsy_words() -> None:
    assert settings_registry.coerce("transcript.enabled", "yes") is True
    assert settings_registry.coerce("transcript.enabled", "off") is False


def test_coerce_bool_rejects_nonsense() -> None:
    with pytest.raises(settings_registry.InvalidSettingValueError):
        settings_registry.coerce("transcript.enabled", "maybe")


def test_coerce_choice_enforces_allowed_values() -> None:
    assert settings_registry.coerce("logging.level", "debug") == "debug"
    with pytest.raises(settings_registry.InvalidSettingValueError):
        settings_registry.coerce("logging.level", "loud")


def test_coerce_optional_clears_to_none() -> None:
    assert settings_registry.coerce("companion.name", "") is None
    assert settings_registry.coerce("companion.name", "none") is None
    assert settings_registry.coerce("companion.name", "Dan") == "Dan"


def test_coerce_required_string_rejects_empty() -> None:
    with pytest.raises(settings_registry.InvalidSettingValueError):
        settings_registry.coerce("client.default", "")


def test_unknown_key_raises() -> None:
    with pytest.raises(settings_registry.UnknownSettingError):
        settings_registry.coerce("nope.key", "x")
    with pytest.raises(settings_registry.UnknownSettingError):
        settings_registry.default_for("nope.key")


def test_load_reads_scalars_and_ignores_structural_tables(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        '[client]\ndefault = "cursor"\n'
        '[profile]\ndefault_role = "qa"\n'
        '[[hooks]]\nphase = "pre-launch"\nspec = "x"\n'  # structural: ignored, must not raise
        '[compress.prompts]\nrules = "/p.txt"\n',  # structural: ignored
    )
    settings = settings_registry.load(path)
    assert settings.client.default == "cursor"
    assert settings.profile.default_role == "qa"
    assert settings.profile.default_environment == "work"  # unset → default


def test_load_is_tolerant_of_missing_and_malformed(tmp_path: Path) -> None:
    assert settings_registry.load(tmp_path / "missing.toml").client.default == "claude"
    malformed = _write(tmp_path, "not : valid = [[[")
    assert settings_registry.load(malformed).client.default == "claude"


def test_config_defaults_match_the_registry(tmp_path: Path) -> None:
    # Single source of truth: config.py's tolerant fallbacks must equal the registry
    # defaults, so a default is never quietly forked between the two.
    missing = tmp_path / "missing.toml"
    assert config.default_client(missing) == settings_registry.default_for("client.default")
    assert config.default_role(missing) == settings_registry.default_for("profile.default_role")
    assert config.default_environment(missing) == settings_registry.default_for(
        "profile.default_environment"
    )
    assert config.log_level(missing) == settings_registry.default_for("logging.level")
    compress = config.compress(missing)
    assert compress.adapter == settings_registry.default_for("compress.adapter")
    assert compress.model == settings_registry.default_for("compress.model")
    assert compress.effort == settings_registry.default_for("compress.effort")


# ── table settings (a key whose value is a map of entries) ──
def test_a_table_setting_is_reported_as_one() -> None:
    assert settings_registry.is_table("client.args") is True
    assert settings_registry.is_table("client.default") is False


def test_a_table_setting_renders_its_own_type_label() -> None:
    row = next(r for r in settings_registry.registry_rows() if r.key == "client.args")
    assert row.type_name == "table"
    assert row.default == {}


def test_an_entry_argument_splits_into_name_and_value() -> None:
    # The entry name rides in the VALUE, not the key, so the dotted key stays two levels
    # and lookup/help/validation need no special case for it.
    assert settings_registry.parse_entry("client.args", "claude=--yolo") == ("claude", "--yolo")


def test_an_entry_value_may_itself_contain_an_equals_sign() -> None:
    assert settings_registry.parse_entry("client.args", "codex=-c model=o3") == (
        "codex",
        "-c model=o3",
    )


def test_an_empty_entry_value_means_clear_it() -> None:
    assert settings_registry.parse_entry("client.args", "claude=") == ("claude", None)


def test_an_entry_argument_without_an_equals_is_rejected() -> None:
    with pytest.raises(settings_registry.InvalidSettingValueError):
        settings_registry.parse_entry("client.args", "claude")


def test_an_entry_argument_without_a_name_is_rejected() -> None:
    with pytest.raises(settings_registry.InvalidSettingValueError):
        settings_registry.parse_entry("client.args", "=--yolo")


def test_coercing_a_table_setting_is_a_programming_error() -> None:
    # A table's persisted value is the whole merged map, which needs the file's current
    # contents — outside what coercing one raw string can know.
    with pytest.raises(TypeError):
        settings_registry.coerce("client.args", "claude=--yolo")
