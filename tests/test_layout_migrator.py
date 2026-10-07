# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem layout migrator: profile/company -> environments/<env>."""

from pathlib import Path

from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_layout_migrator import (
    FilesystemLayoutMigrator,
)


def _company(home: Path) -> Path:
    company = home / "profile" / "company"
    company.mkdir(parents=True)
    return company


def test_no_old_layout_is_a_noop(tmp_path: Path) -> None:
    report = FilesystemLayoutMigrator(tmp_path).migrate("work")
    assert not report.did_anything
    assert report.environment == "work"


def test_moves_company_into_the_environment(tmp_path: Path) -> None:
    company = _company(tmp_path)
    (company / "stack.md").write_text("hexagonal", encoding="utf-8")
    (company / "policies.md").write_text("test first", encoding="utf-8")

    report = FilesystemLayoutMigrator(tmp_path).migrate("work")

    assert sorted(report.moved) == ["policies.md", "stack.md"]
    assert report.skipped == []
    target = tmp_path / "environments" / "work"
    assert (target / "stack.md").read_text(encoding="utf-8") == "hexagonal"
    assert (target / "policies.md").read_text(encoding="utf-8") == "test first"
    assert not (tmp_path / "profile" / "company").exists()  # emptied old layout is retired


def test_migrates_into_the_active_environment_name(tmp_path: Path) -> None:
    company = _company(tmp_path)
    (company / "co.md").write_text("acme", encoding="utf-8")
    report = FilesystemLayoutMigrator(tmp_path).migrate("acme-corp")
    assert report.environment == "acme-corp"
    assert (tmp_path / "environments" / "acme-corp" / "co.md").read_text(encoding="utf-8") == "acme"


def test_moves_subdirectories_too(tmp_path: Path) -> None:
    company = _company(tmp_path)
    (company / "sub").mkdir()
    (company / "sub" / "deep.md").write_text("nested", encoding="utf-8")
    report = FilesystemLayoutMigrator(tmp_path).migrate("work")
    assert report.moved == ["sub"]
    assert (tmp_path / "environments" / "work" / "sub" / "deep.md").read_text(
        encoding="utf-8"
    ) == "nested"


def test_never_overwrites_a_colliding_target_entry(tmp_path: Path) -> None:
    company = _company(tmp_path)
    (company / "stack.md").write_text("OLD from company", encoding="utf-8")
    (company / "fresh.md").write_text("moves cleanly", encoding="utf-8")
    target = tmp_path / "environments" / "work"
    target.mkdir(parents=True)
    (target / "stack.md").write_text("KEEP from env", encoding="utf-8")

    report = FilesystemLayoutMigrator(tmp_path).migrate("work")

    assert report.moved == ["fresh.md"]
    assert report.skipped == ["stack.md"]
    assert (target / "stack.md").read_text(encoding="utf-8") == "KEEP from env"  # not overwritten
    # The colliding source is left in place (surfaced), so the old dir is NOT removed.
    assert (tmp_path / "profile" / "company" / "stack.md").read_text(encoding="utf-8") == (
        "OLD from company"
    )


def test_is_idempotent_across_runs(tmp_path: Path) -> None:
    company = _company(tmp_path)
    (company / "co.md").write_text("acme", encoding="utf-8")
    migrator = FilesystemLayoutMigrator(tmp_path)
    first = migrator.migrate("work")
    second = migrator.migrate("work")
    assert first.moved == ["co.md"]
    assert not second.did_anything  # old layout gone -> no-op
