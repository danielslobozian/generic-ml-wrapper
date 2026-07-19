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
        "language.code",
        "profile.default_role",
        "profile.default_environment",
        "logging.level",
        "companion.persona",
        "companion.name",
        "transcript.enabled",
        "transcript.root",
        "compress.adapter",
        "compress.model",
        "compress.effort",
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
