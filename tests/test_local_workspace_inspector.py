# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the LocalGitWorkspaceInspector against real directories and git repos."""

import subprocess
from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.workspace.local_workspace_inspector import (
    LocalGitWorkspaceInspector,
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=Test", *args],  # noqa: S607
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_outside_a_repo_reports_only_the_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = LocalGitWorkspaceInspector().inspect()
    assert workspace.branch is None
    assert workspace.repo is None
    assert workspace.short_sha is None
    assert workspace.dirty == 0
    assert workspace.folder is not None


def test_folder_abbreviates_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)

    def _home() -> Path:
        return tmp_path

    monkeypatch.setattr(Path, "home", staticmethod(_home))
    assert LocalGitWorkspaceInspector().inspect().folder == "~/proj"


def test_inside_a_clean_repo_reports_git_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "checkout", "-B", "work")
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    monkeypatch.chdir(tmp_path)

    workspace = LocalGitWorkspaceInspector().inspect()
    assert workspace.repo == tmp_path.name
    assert workspace.branch == "work"
    assert workspace.short_sha is not None
    assert workspace.dirty == 0


def test_inside_a_dirty_repo_counts_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "checkout", "-B", "work")
    (tmp_path / "committed.txt").write_text("v1", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    (tmp_path / "committed.txt").write_text("v2", encoding="utf-8")
    (tmp_path / "untracked.txt").write_text("new", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert LocalGitWorkspaceInspector().inspect().dirty == 2
