# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for reading the changelog into releases, and picking the unseen ones."""

from __future__ import annotations

import tomllib
from pathlib import Path

from generic_ml_wrapper import __version__
from generic_ml_wrapper.application.domain.model.release_note import ReleaseNote
from generic_ml_wrapper.application.domain.service.changelog import notes_since, parse_changelog

_ROOT = Path(__file__).resolve().parents[1]

_CHANGELOG = """# Changelog

All notable changes are documented here.

## [Unreleased]

## [0.13.0] - 2026-11-01

### Added
- **gmlw update.**

## [0.12.1] - 2026-10-11

### Fixed
- A fix.

## [0.12.0]

- Something.

[Unreleased]: https://example.org/compare/v0.13.0...HEAD
[0.13.0]: https://example.org/compare/v0.12.1...v0.13.0
"""


def test_each_release_with_an_entry_is_read_newest_first() -> None:
    assert parse_changelog(_CHANGELOG) == (
        ReleaseNote("0.13.0", "2026-11-01", "### Added\n- **gmlw update.**"),
        ReleaseNote("0.12.1", "2026-10-11", "### Fixed\n- A fix."),
        ReleaseNote("0.12.0", None, "- Something."),
    )


def test_a_changelog_without_releases_has_none() -> None:
    assert parse_changelog("# Changelog\n\nNothing yet.\n") == ()


def test_the_unseen_releases_are_those_after_the_seen_up_to_the_running() -> None:
    notes = parse_changelog(_CHANGELOG)
    assert [n.version for n in notes_since(notes, "0.12.0", "0.13.0")] == ["0.13.0", "0.12.1"]
    assert [n.version for n in notes_since(notes, "0.12.0", "0.12.1")] == ["0.12.1"]
    assert notes_since(notes, "0.13.0", "0.13.0") == ()


def test_an_unreadable_version_shows_nothing() -> None:
    notes = parse_changelog(_CHANGELOG)
    assert notes_since(notes, "garbage", "0.13.0") == ()


def test_the_shipped_changelog_has_an_entry_for_the_running_version() -> None:
    notes = parse_changelog((_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert __version__ in [note.version for note in notes]


def test_the_wheel_ships_the_repository_changelog() -> None:
    with (_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)
    included = project["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    assert included["CHANGELOG.md"] == "generic_ml_wrapper/resources/CHANGELOG.md"
