# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the layout seeder and the Bootstrap use case."""

import tomllib
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_layout_seeder import (
    FilesystemLayoutSeeder,
)
from generic_ml_wrapper.application.port.outbound.layout_seeder import (
    InitPersist,
    InitSelections,
    LayoutSeederPort,
)
from generic_ml_wrapper.application.usecase.bootstrap import BootstrapUseCase


def test_seeder_creates_the_layout_and_config(tmp_path: Path) -> None:
    FilesystemLayoutSeeder(tmp_path).ensure()
    assert (tmp_path / "profile" / "me").is_dir()
    assert not (tmp_path / "profile" / "company").exists()  # retired; env folders replace it
    assert (tmp_path / "rules").is_dir()
    config = tmp_path / "config.toml"
    assert config.is_file()
    # The seeded config is valid TOML that parses to no active settings (all commented).
    # The init-owned tables are present as empty tables — bootstrap never stamps the
    # [init] marker (so the gate still forces init) nor bakes in language/profile values.
    assert tomllib.loads(config.read_text(encoding="utf-8")) == {
        "client": {},
        "callers": {},
        "logging": {},
        "companion": {},
        "transcript": {},
        "compress": {},
        "language": {},
        "profile": {},
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
        "language": {},
        "profile": {},
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


def test_initialize_writes_a_full_config_on_a_fresh_install(tmp_path: Path) -> None:
    persisted = FilesystemLayoutSeeder(tmp_path).initialize(
        InitSelections(
            version="0.4.0",
            language="fr",
            name="Daniel",
            role="engineer",
            environment="work",
            persona="butler",
            client="claude",
        )
    )
    assert persisted.fresh is True  # a brand-new install got the full write
    assert persisted.overwrites == ()  # nothing pre-existed to replace
    assert (tmp_path / "environments" / "work").is_dir()  # the chosen environment's folder
    assert (tmp_path / "profile" / "roles" / "engineer" / "rules").is_dir()  # the role's drop-zone
    parsed = tomllib.loads((tmp_path / "config.toml").read_text(encoding="utf-8"))
    assert parsed["init"] == {"version": "0.4.0"}  # the gate marker
    assert parsed["language"] == {"code": "fr"}
    assert parsed["profile"] == {"default_role": "engineer", "default_environment": "work"}
    assert parsed["companion"] == {"name": "Daniel", "persona": "butler"}
    assert parsed["client"] == {"default": "claude"}


def test_initialize_merges_every_answer_into_a_legacy_config(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    # A pre-0.4.0 config with a hand-written comment and settings init does not own.
    legacy = (
        "# my notes\n"
        '[client]\ndefault = "cursor"\n\n'
        '[logging]\nlevel = "debug"\n\n'
        '[companion]\npersona = "mentor"\n'
    )
    config.write_text(legacy, encoding="utf-8")

    persisted = FilesystemLayoutSeeder(tmp_path).initialize(
        InitSelections(
            version="0.4.0",
            language="fr",
            name="Daniel",
            role="engineer",
            environment="work",
            persona="butler",
            client="claude",
        )
    )

    assert persisted.fresh is False  # legacy install: merged, not a fresh write
    text = config.read_text(encoding="utf-8")
    assert "# my notes" in text  # the user's comment survives the round-trip edit
    parsed = tomllib.loads(text)
    # Every captured answer is now persisted...
    assert parsed["init"] == {"version": "0.4.0"}
    assert parsed["language"] == {"code": "fr"}
    assert parsed["profile"] == {"default_role": "engineer", "default_environment": "work"}
    assert parsed["companion"] == {"name": "Daniel", "persona": "butler"}
    assert parsed["client"] == {"default": "claude"}
    # ...settings init does not own are left exactly as they were.
    assert parsed["logging"] == {"level": "debug"}
    # The two values the fresh choice replaced are surfaced, not dropped silently.
    assert set(persisted.overwrites) == {
        "client.default: cursor → claude",
        "companion.persona: mentor → butler",
    }


def test_initialize_does_not_clear_settings_when_persona_or_client_declined(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[companion]\npersona = "mentor"\n[client]\ndefault = "cursor"\n', "utf-8")

    persisted = FilesystemLayoutSeeder(tmp_path).initialize(
        InitSelections(
            version="0.4.0",
            language="en",
            name="Ada",
            role="default",
            environment="work",
            persona=None,  # declined — must not clear the existing persona
            client=None,  # none chosen — must not clear the existing default
        )
    )

    parsed = tomllib.loads(config.read_text(encoding="utf-8"))
    assert parsed["companion"] == {"persona": "mentor", "name": "Ada"}  # kept + name added
    assert parsed["client"] == {"default": "cursor"}  # untouched
    assert persisted.overwrites == ()  # nothing replaced


def test_use_case_delegates_to_the_seeder() -> None:
    calls: list[str] = []

    class FakeSeeder(LayoutSeederPort):
        def ensure(self, default_client: str | None = None, persona: str | None = None) -> None:
            calls.append(f"ensure:{default_client}:{persona}")

        def initialize(self, selections: InitSelections) -> InitPersist:
            calls.append("initialize")
            return InitPersist(fresh=True)

    BootstrapUseCase(FakeSeeder()).execute()
    assert calls == ["ensure:None:None"]
