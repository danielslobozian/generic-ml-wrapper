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
    assert settings.prompts == {}  # no prompt resolves -> every source verbatim
    assert settings.adapter == "cursor"
    assert settings.model == "gpt-5.4"
    assert settings.effort == "low"


def test_compress_reads_overrides(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        '[compress]\nadapter = "vibe"\nmodel = "mistral-medium-3.5"\neffort = "high"\n\n'
        '[compress.prompts]\n"human-touch" = "/kind.md"\n"me.user" = "/key.md"\nbogus = 3\n',
    )
    settings = config.compress(path)
    assert settings.adapter == "vibe"
    assert settings.model == "mistral-medium-3.5"
    assert settings.effort == "high"
    # only string prompt paths survive; the bogus int is dropped
    assert settings.prompts == {"human-touch": "/kind.md", "me.user": "/key.md"}


def test_compress_prompt_for_prefers_key_over_kind(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        '[compress.prompts]\n"human-touch" = "/kind.md"\n"me.user" = "/key.md"\n',
    )
    settings = config.compress(path)
    assert settings.prompt_for("me.user", "human-touch") == "/key.md"  # key wins
    assert settings.prompt_for("me.learned", "human-touch") == "/kind.md"  # falls to kind
    assert settings.prompt_for("company", None) is None  # no key, no kind -> verbatim


def test_default_startup_matrix_per_mode() -> None:
    default = config.default_startup("default")
    assert default["me.user"].activated is True
    assert default["rules"].activated is True  # rules (+ capture directive) on in a plain start
    assert default["persona"].activated is False
    assert all(setting.compression is False for setting in default.values())
    workflow = config.default_startup("workflow")
    assert workflow["rules"].activated is True  # rules on for a workflow
    assert workflow["base"].activated is True  # intrinsic
    assert workflow["steps"].activated is True


def test_startup_reads_activation_and_compression_over_defaults(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "[startup.default.context.me]\n"
        "user = { activated = true, compression = true }\n\n"
        "[startup.default.context]\n"
        "company = { activated = false }\n"
        "persona = { activated = true }\n",
    )
    settings = config.startup("default", path)
    assert settings["me.user"].compression is True  # overridden on
    assert settings["company"].activated is False  # overridden off
    assert settings["persona"].activated is True  # overridden on
    assert settings["me.learned"].activated is True  # untouched -> default


def test_startup_ignores_activation_for_intrinsic_base_and_steps(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "[startup.workflow.context]\n"
        "base = { activated = false, compression = true }\n"
        "steps = { activated = false }\n",
    )
    settings = config.startup("workflow", path)
    assert settings["base"].activated is True  # intrinsic: cannot be deactivated
    assert settings["base"].compression is True  # but compression is honored
    assert settings["steps"].activated is True


def test_companion_defaults_to_no_persona(tmp_path: Path) -> None:
    assert config.companion(tmp_path / "missing.toml").persona is None  # invisible by default


def test_companion_reads_the_selected_persona(tmp_path: Path) -> None:
    path = _write(tmp_path, '[companion]\npersona = "butler"\n')
    assert config.companion(path).persona == "butler"


def test_transcript_defaults_off(tmp_path: Path) -> None:
    assert config.transcript(tmp_path / "none.toml").enabled is False


def test_transcript_reads_enabled_and_root(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[transcript]\nenabled = true\nroot = "/some/dir"\n', encoding="utf-8")
    settings = config.transcript(path)
    assert settings.enabled is True
    assert settings.root == "/some/dir"
