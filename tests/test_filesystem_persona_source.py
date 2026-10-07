# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem persona source (seeds the packaged personas)."""

from pathlib import Path

from generic_ml_wrapper.adapter.outbound.persona.filesystem_persona_source import (
    FilesystemPersonaSource,
)

_BUILT_IN = {"plain", "companion", "mentor", "butler", "terse"}


def test_available_seeds_and_lists_the_built_in_personas(tmp_path: Path) -> None:
    personas = FilesystemPersonaSource(tmp_path / "personas").available()
    names = [persona.name for persona in personas]
    assert set(names) == _BUILT_IN
    assert names == sorted(names)  # sorted by name
    assert all(persona.description for persona in personas)  # each carries a description


def test_available_excludes_the_floor(tmp_path: Path) -> None:
    source = FilesystemPersonaSource(tmp_path / "personas")
    assert "_floor" not in {persona.name for persona in source.available()}
    assert source.floor()  # but the floor is readable on its own


def test_get_returns_a_persona_with_its_greeting_and_body(tmp_path: Path) -> None:
    persona = FilesystemPersonaSource(tmp_path / "personas").get("butler")
    assert persona is not None
    assert persona.name == "butler"
    assert "{daypart}" in persona.greeting  # greeting template preserved
    assert "Identity" in persona.body


def test_get_unknown_or_underscored_is_none(tmp_path: Path) -> None:
    source = FilesystemPersonaSource(tmp_path / "personas")
    assert source.get("nope") is None
    assert source.get("_floor") is None  # the floor is not a selectable persona


def test_seed_never_overwrites_a_user_edit(tmp_path: Path) -> None:
    root = tmp_path / "personas"
    root.mkdir()
    (root / "butler.md").write_text("MINE", encoding="utf-8")
    source = FilesystemPersonaSource(root)
    source.seed()
    persona = source.get("butler")
    assert persona is not None
    assert persona.body == "MINE"  # user edit preserved
