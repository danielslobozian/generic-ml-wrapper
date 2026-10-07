# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the FilesystemAxisCatalog adapter (real filesystem under tmp_path)."""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_axis_catalog import (
    FilesystemAxisCatalog,
)
from generic_ml_wrapper.application.domain.model.axis import AxisKind

_WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _catalog(home: Path) -> FilesystemAxisCatalog:
    return FilesystemAxisCatalog(home, clock=lambda: _WHEN)


def test_create_environment_writes_folder_and_about(tmp_path: Path) -> None:
    _catalog(tmp_path).create(
        AxisKind.ENVIRONMENT, "client-project", "Client Project", "the gig", _WHEN.isoformat()
    )
    folder = tmp_path / "environments" / "client-project"
    assert folder.is_dir()
    about = tomllib.loads((folder / ".about.toml").read_text(encoding="utf-8"))
    assert about["label"] == "Client Project"
    assert about["description"] == "the gig"
    assert about["created"] == _WHEN.isoformat()


def test_create_role_adds_a_rules_dropzone(tmp_path: Path) -> None:
    _catalog(tmp_path).create(
        AxisKind.ROLE, "code-reviewer", "Code Reviewer", "", _WHEN.isoformat()
    )
    role = tmp_path / "profile" / "roles" / "code-reviewer"
    assert role.is_dir()
    assert (role / "rules").is_dir()  # role-scoped reflexes drop-zone
    assert (role / ".about.toml").exists()


def test_exists_reflects_the_folder(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    assert catalog.exists(AxisKind.ENVIRONMENT, "work") is False
    catalog.create(AxisKind.ENVIRONMENT, "work", "Work", "", _WHEN.isoformat())
    assert catalog.exists(AxisKind.ENVIRONMENT, "work") is True


def test_list_reads_labels_and_sorts_by_slug(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    catalog.create(AxisKind.ENVIRONMENT, "work", "Work", "the day job", _WHEN.isoformat())
    catalog.create(AxisKind.ENVIRONMENT, "client-project", "Client Project", "", _WHEN.isoformat())
    entries = catalog.list(AxisKind.ENVIRONMENT)
    assert [(e.slug, e.label) for e in entries] == [
        ("client-project", "Client Project"),
        ("work", "Work"),
    ]


def test_list_is_empty_when_the_root_is_missing(tmp_path: Path) -> None:
    assert _catalog(tmp_path).list(AxisKind.ROLE) == []
