# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem workflow backup: displacing a workflow, and putting it back.

Against the real filesystem rather than fakes, because every claim here is about what the
disk actually does — that a move lands where it says, that a second backup in the same
second does not end up inside the first, and that a restore leaves nothing of the attempt
that failed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.workflow.filesystem_workflow_backup import (
    FilesystemWorkflowBackupAdapter,
)
from generic_ml_wrapper.application.domain.model.workflow_backup import WorkflowBackup

_WHEN = datetime(2026, 7, 29, 15, 30, 12, tzinfo=UTC)


def _backups(tmp_path: Path) -> FilesystemWorkflowBackupAdapter:
    return FilesystemWorkflowBackupAdapter(tmp_path / "backups", lambda: _WHEN)


def _a_workflow(tmp_path: Path, name: str = "nightly-etl", body: str = "the old one") -> Path:
    folder = tmp_path / "workflows" / name
    folder.mkdir(parents=True)
    (folder / "workflow.md").write_text(body, encoding="utf-8")
    return folder


def test_displacing_moves_the_folder_and_says_where(tmp_path: Path) -> None:
    folder = _a_workflow(tmp_path)

    backup = _backups(tmp_path).displace("nightly-etl", str(folder))

    assert backup is not None
    assert not folder.exists()  # left free for the replacement
    assert (tmp_path / "backups" / "nightly-etl" / "20260729-153012" / "workflow.md").read_text(
        encoding="utf-8"
    ) == "the old one"
    assert backup.location == str(tmp_path / "backups" / "nightly-etl" / "20260729-153012")


def test_displacing_an_empty_folder_reports_nothing_was_there(tmp_path: Path) -> None:
    """So a caller can ask without first looking at the disk to find out whether to."""
    assert _backups(tmp_path).displace("ghost", str(tmp_path / "workflows" / "ghost")) is None


def test_the_backup_lives_outside_the_workflows_folder(tmp_path: Path) -> None:
    # A folder under `workflows` with a workflow.md lists as runnable, so keeping backups
    # out makes "a backup is never a workflow" structural rather than a filter.
    backup = _backups(tmp_path).displace("nightly-etl", str(_a_workflow(tmp_path)))

    assert backup is not None
    assert (tmp_path / "workflows") not in Path(backup.location).parents


def test_a_second_backup_in_the_same_second_does_not_land_inside_the_first(
    tmp_path: Path,
) -> None:
    """A directory moved onto an existing directory goes *inside* it rather than failing.

    Second-resolution names alone would therefore bury the older copy — which is the one a
    user replacing twice in a row is most likely to want back.
    """
    backups = _backups(tmp_path)
    first = backups.displace("nightly-etl", str(_a_workflow(tmp_path, body="the first")))
    second = backups.displace("nightly-etl", str(_a_workflow(tmp_path, body="the second")))

    assert first is not None
    assert second is not None
    assert first.location != second.location
    assert Path(first.location, "workflow.md").read_text(encoding="utf-8") == "the first"
    assert Path(second.location, "workflow.md").read_text(encoding="utf-8") == "the second"
    # Not nested: the second is a sibling, not a child of the first.
    assert Path(first.location) not in Path(second.location).parents


def test_restoring_puts_the_workflow_back(tmp_path: Path) -> None:
    folder = _a_workflow(tmp_path)
    backups = _backups(tmp_path)
    backup = backups.displace("nightly-etl", str(folder))
    assert backup is not None

    backups.restore(backup, str(folder))

    assert (folder / "workflow.md").read_text(encoding="utf-8") == "the old one"
    assert not Path(backup.location).exists()


def test_restoring_discards_whatever_replaced_it(tmp_path: Path) -> None:
    """A half-written replacement is not something to merge the original back into."""
    folder = _a_workflow(tmp_path)
    backups = _backups(tmp_path)
    backup = backups.displace("nightly-etl", str(folder))
    assert backup is not None
    folder.mkdir(parents=True)
    (folder / "half-written").write_text("junk", encoding="utf-8")

    backups.restore(backup, str(folder))

    assert (folder / "workflow.md").read_text(encoding="utf-8") == "the old one"
    assert not (folder / "half-written").exists()


def test_restoring_into_a_folder_that_was_never_recreated_works(tmp_path: Path) -> None:
    """The ordinary case: unpacking failed before it made anything."""
    folder = _a_workflow(tmp_path)
    backups = _backups(tmp_path)
    backup = backups.displace("nightly-etl", str(folder))
    assert backup is not None

    backups.restore(backup, str(folder))

    assert (folder / "workflow.md").is_file()


def test_a_backup_must_know_its_name_and_where_it_is() -> None:
    with pytest.raises(ValueError, match="name must not be empty"):
        WorkflowBackup("", "/somewhere")
    with pytest.raises(ValueError, match="location must not be empty"):
        WorkflowBackup("nightly-etl", "")
