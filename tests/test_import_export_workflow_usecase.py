# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for exporting and importing a workflow, driven by fakes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from generic_ml_wrapper.application.domain.model.archive_status import ArchiveStatus
from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.draft import Draft, DraftMarker
from generic_ml_wrapper.application.domain.model.workflow import Workflow
from generic_ml_wrapper.application.port.inbound.edit_workflow import WorkflowNotFoundError
from generic_ml_wrapper.application.port.inbound.import_workflow import (
    ArchiveUnreadableError,
    ImportOutcome,
)
from generic_ml_wrapper.application.port.inbound.new_workflow import WorkflowNameError
from generic_ml_wrapper.application.port.outbound.workflow_archive import WorkflowArchivePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.export_workflow import ExportWorkflowUseCase
from generic_ml_wrapper.application.usecase.import_workflow import ImportWorkflowUseCase

_WHEN = datetime(2026, 7, 29, 15, 30, 12, tzinfo=UTC)


class FakeWorkflows(WorkflowSourcePort):
    def __init__(self, root: Path, existing: set[str] | None = None) -> None:
        self._root = root
        self._existing = existing or set()
        self.seeded = False

    def seed(self) -> None:
        self.seeded = True

    def names(self) -> list[str]:
        return sorted(self._existing)

    def catalog(self) -> list[Workflow]:
        return []

    def exists(self, name: str) -> bool:
        return name in self._existing

    def create(self, name: str) -> str:
        raise NotImplementedError

    def folder(self, name: str) -> str:
        return str(self._root / name)

    def drafts(self) -> list[Draft]:
        return []

    def create_draft(self, key: str) -> str:
        raise NotImplementedError

    def read_draft_marker(self, draft_path: str) -> DraftMarker:
        raise NotImplementedError

    def deploy_draft(
        self, draft_path: str, name: str, label: str, description: str, created: str
    ) -> str:
        raise NotImplementedError

    def meta_guide(self) -> str:
        return ""

    def compile(self, mode: CompileMode, name: str | None = None, job: str | None = None) -> str:
        return ""


class FakeArchive(WorkflowArchivePort):
    """Records what it was asked to do, and writes a marker file on unpack.

    ``status`` is what :meth:`inspect` reports for an archive that exists; ``fail_unpack``
    makes unpacking write part of a workflow and then raise, like a disk filling up.
    """

    def __init__(
        self, status: ArchiveStatus = ArchiveStatus.COMPLETE, *, fail_unpack: bool = False
    ) -> None:
        self.packed: tuple[Path, str] | None = None
        self.unpacked: tuple[Path, Path] | None = None
        self._status = status
        self._fail_unpack = fail_unpack

    def inspect(self, archive: Path) -> ArchiveStatus:
        return self._status if archive.is_file() else ArchiveStatus.MISSING

    def pack(self, folder: Path, slug: str) -> Path:
        self.packed = (folder, slug)
        return Path(f"/exports/{slug}.zip")

    def unpack(self, archive: Path, destination: Path) -> None:
        self.unpacked = (archive, destination)
        destination.mkdir(parents=True, exist_ok=True)
        if self._fail_unpack:
            (destination / "scripts").mkdir()
            raise OSError("No space left on device")
        (destination / "workflow.md").write_text("# steps", encoding="utf-8")


# ── export ──
def test_exporting_packs_the_workflows_own_folder(tmp_path: Path) -> None:
    archive = FakeArchive()
    written = ExportWorkflowUseCase(FakeWorkflows(tmp_path, {"nightly-etl"}), archive).execute(
        "nightly-etl"
    )
    assert archive.packed == (tmp_path / "nightly-etl", "nightly-etl")
    # Through Path, so the separator is the platform's -- the claim is that the archive's
    # own path comes back, not that it is spelled with a slash.
    assert written == str(Path("/exports/nightly-etl.zip"))


def test_exporting_an_unknown_workflow_is_refused(tmp_path: Path) -> None:
    workflows = FakeWorkflows(tmp_path)
    with pytest.raises(WorkflowNotFoundError):
        ExportWorkflowUseCase(workflows, FakeArchive()).execute("ghost")
    # `gmlw workflow export ghost` on a fresh home used to create ~/.gmlw/workflows.
    assert workflows.seeded is False


@pytest.mark.parametrize("name", ["_common", "create-workflow", "Bad Name"])
def test_exporting_a_reserved_or_invalid_name_is_refused(tmp_path: Path, name: str) -> None:
    with pytest.raises(WorkflowNameError):
        ExportWorkflowUseCase(FakeWorkflows(tmp_path, {name}), FakeArchive()).execute(name)


# ── import ──
def _use_case(
    tmp_path: Path, existing: set[str] | None = None, archive: FakeArchive | None = None
) -> ImportWorkflowUseCase:
    return ImportWorkflowUseCase(
        FakeWorkflows(tmp_path / "workflows", existing),
        archive or FakeArchive(),
        tmp_path / "backups",
        lambda: _WHEN,
    )


def _an_archive(tmp_path: Path, name: str = "nightly-etl.zip") -> str:
    path = tmp_path / name
    path.write_bytes(b"PK")
    return str(path)


def test_importing_installs_the_workflow(tmp_path: Path) -> None:
    result = _use_case(tmp_path).execute(_an_archive(tmp_path))
    assert result.outcome is ImportOutcome.IMPORTED
    assert result.name == "nightly-etl"
    assert result.backup is None
    assert Path(result.path, "workflow.md").is_file()


def test_an_existing_name_is_reported_rather_than_overwritten(tmp_path: Path) -> None:
    # The use case does not resolve the clash: it reports it so a caller can ask a
    # person first. Nothing is touched.
    (tmp_path / "workflows" / "nightly-etl").mkdir(parents=True)
    result = _use_case(tmp_path, {"nightly-etl"}).execute(_an_archive(tmp_path))
    assert result.outcome is ImportOutcome.REFUSED
    assert result.backup is None


def test_replacing_moves_the_old_workflow_to_a_timestamped_backup(tmp_path: Path) -> None:
    existing = tmp_path / "workflows" / "nightly-etl"
    existing.mkdir(parents=True)
    (existing / "workflow.md").write_text("the old one", encoding="utf-8")

    result = _use_case(tmp_path, {"nightly-etl"}).execute(_an_archive(tmp_path), replace=True)

    assert result.outcome is ImportOutcome.REPLACED
    assert result.backup == str(tmp_path / "backups" / "nightly-etl" / "20260729-153012")
    assert result.backup is not None
    # Moved, not deleted: replacing is never a one-way door.
    assert Path(result.backup, "workflow.md").read_text(encoding="utf-8") == "the old one"
    assert Path(result.path, "workflow.md").read_text(encoding="utf-8") == "# steps"


def test_the_backup_lives_outside_the_workflows_folder(tmp_path: Path) -> None:
    # The requirement: a backup must never be listed as a workflow. Keeping it out of
    # the workflows root makes that structural rather than a filter to remember.
    existing = tmp_path / "workflows" / "nightly-etl"
    existing.mkdir(parents=True)
    result = _use_case(tmp_path, {"nightly-etl"}).execute(_an_archive(tmp_path), replace=True)
    assert result.backup is not None
    assert (tmp_path / "workflows") not in Path(result.backup).parents


def test_a_missing_archive_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ArchiveUnreadableError):
        _use_case(tmp_path).execute(str(tmp_path / "nope.zip"))


def test_an_export_timestamp_is_stripped_from_the_name(tmp_path: Path) -> None:
    # Exports are named <slug>-<date>-<time>.zip; importing one must not create a
    # workflow called "nightly-etl-20260729-153012".
    result = _use_case(tmp_path).execute(_an_archive(tmp_path, "nightly-etl-20260729-153012.zip"))
    assert result.name == "nightly-etl"


def test_an_archive_named_for_a_reserved_workflow_is_refused(tmp_path: Path) -> None:
    with pytest.raises(WorkflowNameError):
        _use_case(tmp_path).execute(_an_archive(tmp_path, "create-workflow.zip"))


def _an_installed_workflow(tmp_path: Path) -> Path:
    existing = tmp_path / "workflows" / "nightly-etl"
    existing.mkdir(parents=True)
    (existing / "workflow.md").write_text("the old one", encoding="utf-8")
    return existing


def test_an_archive_without_a_workflow_leaves_the_installed_one_in_place(tmp_path: Path) -> None:
    # The archive is asked what it is before anything moves: the wrong file is refused
    # with the installed workflow untouched, rather than leaving the user with neither.
    existing = _an_installed_workflow(tmp_path)
    use_case = _use_case(tmp_path, {"nightly-etl"}, FakeArchive(ArchiveStatus.INCOMPLETE))

    with pytest.raises(ArchiveUnreadableError):
        use_case.execute(_an_archive(tmp_path), replace=True)

    assert (existing / "workflow.md").read_text(encoding="utf-8") == "the old one"
    assert not (tmp_path / "backups").exists()


def test_a_failed_unpack_puts_the_old_workflow_back(tmp_path: Path) -> None:
    existing = _an_installed_workflow(tmp_path)
    use_case = _use_case(tmp_path, {"nightly-etl"}, FakeArchive(fail_unpack=True))

    with pytest.raises(OSError, match="No space left"):
        use_case.execute(_an_archive(tmp_path), replace=True)

    assert (existing / "workflow.md").read_text(encoding="utf-8") == "the old one"
    # What the failed attempt left behind is discarded, not merged into the old one.
    assert not (existing / "scripts").exists()
    assert list((tmp_path / "backups" / "nightly-etl").iterdir()) == []


def test_a_failed_first_import_leaves_nothing_behind(tmp_path: Path) -> None:
    use_case = _use_case(tmp_path, archive=FakeArchive(fail_unpack=True))
    with pytest.raises(OSError, match="No space left"):
        use_case.execute(_an_archive(tmp_path))
    assert not (tmp_path / "workflows" / "nightly-etl").exists()


def test_two_replacements_in_one_second_keep_both_backups_side_by_side(tmp_path: Path) -> None:
    # Backups are stamped to the second, and moving a folder onto an existing one moves
    # it inside it: without a counter the older backup would nest in the newer one.
    _an_installed_workflow(tmp_path)
    use_case = _use_case(tmp_path, {"nightly-etl"})

    first = use_case.execute(_an_archive(tmp_path), replace=True).backup
    second = use_case.execute(_an_archive(tmp_path), replace=True).backup

    backups = tmp_path / "backups" / "nightly-etl"
    assert first == str(backups / "20260729-153012")
    assert second == str(backups / "20260729-153012-2")
    names = sorted(path.name for path in backups.iterdir())
    assert names == ["20260729-153012", "20260729-153012-2"]
