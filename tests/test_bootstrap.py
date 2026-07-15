# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the layout seeder and the Bootstrap use case."""

import tomllib
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_layout_seeder import (
    FilesystemLayoutSeeder,
)
from generic_ml_wrapper.application.port.outbound.layout_seeder import LayoutSeederPort
from generic_ml_wrapper.application.usecase.bootstrap import BootstrapUseCase


def test_seeder_creates_the_layout_and_config(tmp_path: Path) -> None:
    FilesystemLayoutSeeder(tmp_path).ensure()
    assert (tmp_path / "profile" / "me").is_dir()
    assert (tmp_path / "profile" / "company").is_dir()
    assert (tmp_path / "rules").is_dir()
    config = tmp_path / "config.toml"
    assert config.is_file()
    # The seeded config is valid TOML that parses to no active settings (all commented).
    assert tomllib.loads(config.read_text(encoding="utf-8")) == {
        "client": {},
        "callers": {},
        "logging": {},
        "companion": {},
        "transcript": {},
        "compress": {},
    }


def test_seeder_bakes_in_the_chosen_default_client(tmp_path: Path) -> None:
    FilesystemLayoutSeeder(tmp_path).ensure(default_client="cursor")
    config = tmp_path / "config.toml"
    # The chosen default is an ACTIVE setting; everything else stays commented off.
    assert tomllib.loads(config.read_text(encoding="utf-8")) == {
        "client": {"default": "cursor"},
        "callers": {},
        "logging": {},
        "companion": {},
        "transcript": {},
        "compress": {},
    }


def test_seeder_seeds_the_learned_notebook(tmp_path: Path) -> None:
    FilesystemLayoutSeeder(tmp_path).ensure()
    notebook = tmp_path / "profile" / "me" / "learned.md"
    assert notebook.is_file()
    text = notebook.read_text(encoding="utf-8")
    assert "## What follows you" in text  # the positive section
    assert "## What to avoid" in text  # the negative section (first-class)


def test_seeder_seeds_the_example_rule_as_a_draft(tmp_path: Path) -> None:
    FilesystemLayoutSeeder(tmp_path).ensure()
    example = tmp_path / "rules" / "example.rule.md"
    assert example.is_file()
    text = example.read_text(encoding="utf-8")
    assert "status: draft" in text  # never injected; a template to copy
    for field in ("**Rule:**", "**When:**", "**Signals:**", "**Strength:**", "**Origin:**"):
        assert field in text


def test_seeder_never_overwrites_an_edited_notebook(tmp_path: Path) -> None:
    (tmp_path / "profile" / "me").mkdir(parents=True)
    notebook = tmp_path / "profile" / "me" / "learned.md"
    notebook.write_text("MY NOTES", encoding="utf-8")
    FilesystemLayoutSeeder(tmp_path).ensure()
    assert notebook.read_text(encoding="utf-8") == "MY NOTES"


def test_seeder_bakes_in_the_chosen_persona(tmp_path: Path) -> None:
    FilesystemLayoutSeeder(tmp_path).ensure(persona="butler")
    config = tmp_path / "config.toml"
    parsed = tomllib.loads(config.read_text(encoding="utf-8"))
    assert parsed["companion"] == {"persona": "butler"}  # active; everything else commented
    assert parsed["client"] == {}


def test_seeder_is_idempotent_and_preserves_an_edited_config(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    (tmp_path / "rules").mkdir()
    config.write_text('[client]\ndefault = "cursor"\n', encoding="utf-8")

    FilesystemLayoutSeeder(tmp_path).ensure()  # must not overwrite

    assert 'default = "cursor"' in config.read_text(encoding="utf-8")
    assert (tmp_path / "profile" / "me").is_dir()  # still fills in what was missing


def test_use_case_delegates_to_the_seeder() -> None:
    calls: list[str] = []

    class FakeSeeder(LayoutSeederPort):
        def ensure(self, default_client: str | None = None, persona: str | None = None) -> None:
            calls.append(f"ensure:{default_client}:{persona}")

    BootstrapUseCase(FakeSeeder()).execute()
    assert calls == ["ensure:None:None"]
