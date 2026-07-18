# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the status-line settings install/restore safety."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from generic_ml_wrapper.adapter.outbound.caller import status_line_config
from generic_ml_wrapper.adapter.outbound.caller.status_line_config import SettingsUnreadableError

if TYPE_CHECKING:
    from pathlib import Path

_STATUS: dict[str, object] = {"type": "command", "command": "gmlw statusline"}


def test_absent_file_installs_then_removes(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    snapshot = status_line_config.install(path, _STATUS)
    assert json.loads(path.read_text(encoding="utf-8"))["statusLine"] == _STATUS
    status_line_config.restore(path, snapshot)
    assert "statusLine" not in json.loads(path.read_text(encoding="utf-8"))


def test_preserves_other_keys_and_restores_previous(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"statusLine": "MINE", "model": "opus"}), encoding="utf-8")
    snapshot = status_line_config.install(path, _STATUS)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["statusLine"] == _STATUS
    assert data["model"] == "opus"  # untouched
    status_line_config.restore(path, snapshot)
    assert json.loads(path.read_text(encoding="utf-8"))["statusLine"] == "MINE"


@pytest.mark.parametrize(
    "content",
    [
        '{"statusLine": "MINE",}',  # trailing comma
        "// a comment\n{}",  # comment
        "[1, 2, 3]",  # top-level list, not an object
        "not json at all",
    ],
)
def test_unparseable_file_aborts_and_is_left_untouched(tmp_path: Path, content: str) -> None:
    path = tmp_path / "settings.json"
    path.write_text(content, encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(SettingsUnreadableError):
        status_line_config.install(path, _STATUS)
    assert path.read_bytes() == before  # byte-for-byte: never overwritten


def test_concurrent_runs_never_leave_gmlw_installed(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"statusLine": "USER"}), encoding="utf-8")
    # Run A installs, then Run B installs over it (B snapshots A's gmlw value).
    snapshot_a = status_line_config.install(path, _STATUS)
    snapshot_b = status_line_config.install(path, _STATUS)
    # Restoring A then B: ownership-aware restore converges to the user's original,
    # where the old blind restore left B's snapshot (gmlw) behind.
    status_line_config.restore(path, snapshot_a)
    status_line_config.restore(path, snapshot_b)
    assert json.loads(path.read_text(encoding="utf-8"))["statusLine"] == "USER"


def test_install_best_effort_skips_when_the_file_cannot_be_written(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory", encoding="utf-8")
    path = blocker / "cli-config.json"  # parent is a file -> the write fails with OSError
    assert status_line_config.install_best_effort(path, _STATUS) is None


def test_install_best_effort_still_aborts_on_unparseable_settings(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{ not json", encoding="utf-8")  # unreadable settings stay fatal
    before = path.read_bytes()
    with pytest.raises(SettingsUnreadableError):
        status_line_config.install_best_effort(path, _STATUS)
    assert path.read_bytes() == before  # never overwritten
