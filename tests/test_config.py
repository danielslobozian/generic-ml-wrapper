# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the optional config reader."""

from pathlib import Path

from generic_ml_wrapper.common import config


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_default_client_falls_back_to_claude_when_absent(tmp_path: Path) -> None:
    assert config.default_client(tmp_path / "missing.toml") == "claude"


def test_default_client_reads_the_config(tmp_path: Path) -> None:
    path = _write(tmp_path, '[client]\ndefault = "cursor"\n')
    assert config.default_client(path) == "cursor"


def test_malformed_config_falls_back(tmp_path: Path) -> None:
    path = _write(tmp_path, "this is not : valid = toml [[[")
    assert config.default_client(path) == "claude"
    assert config.caller_overrides(path) == {}


def test_caller_overrides_are_read(tmp_path: Path) -> None:
    path = _write(tmp_path, '[callers]\ncursor = "my_pkg.mod:MyCaller"\nclaude = 3\n')
    # only string values survive; the bogus int entry is dropped
    assert config.caller_overrides(path) == {"cursor": "my_pkg.mod:MyCaller"}


def test_no_callers_section_is_empty(tmp_path: Path) -> None:
    path = _write(tmp_path, '[client]\ndefault = "claude"\n')
    assert config.caller_overrides(path) == {}


def test_interceptors_are_read_in_order(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        '[[interceptors]]\ntarget = "rules"\nspec = "pkg:Compress"\n\n'
        '[[interceptors]]\ntarget = "profile"\nspec = "pkg:Redact"\n\n'
        '[[interceptors]]\nspec = "pkg:NoTarget"\n',  # malformed: dropped
    )
    assert config.interceptors(path) == [("rules", "pkg:Compress"), ("profile", "pkg:Redact")]


def test_no_interceptors_section_is_empty(tmp_path: Path) -> None:
    assert config.interceptors(tmp_path / "missing.toml") == []


def test_log_level_reads_config_and_defaults_to_warning(tmp_path: Path) -> None:
    assert config.log_level(tmp_path / "missing.toml") == "warning"
    path = _write(tmp_path, '[logging]\nlevel = "debug"\n')
    assert config.log_level(path) == "debug"


def test_compress_defaults_off_with_cursor_gpt54_low(tmp_path: Path) -> None:
    settings = config.compress(tmp_path / "missing.toml")
    assert settings.prompt is None  # off until a prompt is set
    assert settings.adapter == "cursor"
    assert settings.model == "gpt-5.4"
    assert settings.effort == "low"


def test_compress_reads_overrides(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        '[compress]\nprompt = "/p.md"\nadapter = "vibe"\nmodel = "mistral-medium-3.5"\n'
        'effort = "high"\n',
    )
    settings = config.compress(path)
    assert settings.prompt == "/p.md"
    assert settings.adapter == "vibe"
    assert settings.model == "mistral-medium-3.5"
    assert settings.effort == "high"


def test_transcript_defaults_off(tmp_path: Path) -> None:
    assert config.transcript(tmp_path / "none.toml").enabled is False


def test_transcript_reads_enabled_and_root(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[transcript]\nenabled = true\nroot = "/some/dir"\n', encoding="utf-8")
    settings = config.transcript(path)
    assert settings.enabled is True
    assert settings.root == "/some/dir"
