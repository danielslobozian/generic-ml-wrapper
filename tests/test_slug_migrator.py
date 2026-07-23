# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the slug migrator: rename legacy raw-named role/environment folders."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_slug_migrator import (
    FilesystemSlugMigrator,
)

if TYPE_CHECKING:
    from pathlib import Path


def _make(home: Path, *, environment: str | None = None, role: str | None = None) -> Path:
    """Create an environment or role folder with a marker file; return it."""
    rel = ("environments", environment) if environment else ("profile", "roles", role or "")
    folder = home.joinpath(*rel)
    folder.mkdir(parents=True)
    (folder / "notes.md").write_text("keep me", encoding="utf-8")
    return folder


def test_renames_raw_folders_writes_about_and_keeps_content(tmp_path: Path) -> None:
    _make(tmp_path, environment="Éqùipe Test")
    _make(tmp_path, role="Senior Engineer")

    report = FilesystemSlugMigrator(tmp_path).migrate()

    assert set(report.renamed) == {
        ("Éqùipe Test", "equipe-test"),
        ("Senior Engineer", "senior-engineer"),
    }
    target = tmp_path / "environments" / "equipe-test"
    assert (target / "notes.md").read_text(encoding="utf-8") == "keep me"  # content moved along
    about = tomllib.loads((target / ".about.toml").read_text(encoding="utf-8"))
    assert about["label"] == "Éqùipe Test"  # the old name is kept as the human label
    assert about["description"] == "Éqùipe Test"
    assert about["created"]  # a best-effort creation stamp was written


def test_repoints_the_config_default_that_named_the_old_folder(tmp_path: Path) -> None:
    _make(tmp_path, environment="Éqùipe Test")
    (tmp_path / "config.toml").write_text(
        '[profile]\ndefault_environment = "Éqùipe Test"\ndefault_role = "keep"\n', encoding="utf-8"
    )
    FilesystemSlugMigrator(tmp_path).migrate()
    parsed = tomllib.loads((tmp_path / "config.toml").read_text(encoding="utf-8"))
    assert parsed["profile"]["default_environment"] == "equipe-test"  # repointed to the new slug
    assert parsed["profile"]["default_role"] == "keep"  # an unrelated default is left alone


def test_is_idempotent_and_leaves_clean_slugs_untouched(tmp_path: Path) -> None:
    _make(tmp_path, environment="work")  # already a slug
    _make(tmp_path, environment="Team A")

    first = FilesystemSlugMigrator(tmp_path).migrate()
    assert first.renamed == [("Team A", "team-a")]  # only the raw one moved

    second = FilesystemSlugMigrator(tmp_path).migrate()
    assert second.renamed == []  # nothing left to do
    assert (tmp_path / "environments" / "work").is_dir()
    assert (tmp_path / "environments" / "team-a").is_dir()


def test_disambiguates_folders_that_slug_to_the_same_name(tmp_path: Path) -> None:
    _make(tmp_path, environment="Team A")
    _make(tmp_path, environment="team a")  # both slug to "team-a"

    report = FilesystemSlugMigrator(tmp_path).migrate()

    assert sorted(new for _, new in report.renamed) == ["team-a", "team-a-2"]
