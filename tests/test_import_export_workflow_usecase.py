# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for exporting and importing a workflow, driven by fakes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.workflow.filesystem_workflow_backup import (
    FilesystemWorkflowBackupAdapter,
)
from generic_ml_wrapper.adapter.outbound.workflow.filesystem_workflow_source import (
    FilesystemWorkflowSourceAdapter,
)
from generic_ml_wrapper.application.domain.model.archive_status import ArchiveStatus
from generic_ml_wrapper.application.domain.model.archive_unreadable_error import (
    ArchiveUnreadableError,
)
from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.draft import Draft, DraftMarker
from generic_ml_wrapper.application.domain.model.workflow import Workflow
from generic_ml_wrapper.application.domain.model.workflow_name_error import WorkflowNameError
from generic_ml_wrapper.application.domain.model.workflow_not_found_error import (
    WorkflowNotFoundError,
)
from generic_ml_wrapper.application.port.inbound.import_outcome import ImportOutcome
from generic_ml_wrapper.application.port.outbound.workflow_archive import WorkflowArchivePort
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.application.usecase.export_workflow import ExportWorkflowService
from generic_ml_wrapper.application.usecase.import_workflow import ImportWorkflowService

_WHEN = datetime(2026, 7, 29, 15, 30, 12, tzinfo=UTC)


class FakeWorkflows(WorkflowSourcePort):
    def __init__(self, root: Path, existing: set[str] | None = None) -> None:
        self._root = root
        self._existing = existing or set()

    def seed(self) -> None: ...
    def names(self) -> list[str]:
        return sorted(self._existing)

    def catalog(self) -> list[Workflow]:
        return []

    def find(self, name: str) -> Workflow | None:
        return Workflow(name, name, "") if name in self._existing else None

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

    ``status`` and ``unpack_fails`` are what a test declares up front: whether the archive
    is worth importing, and whether unpacking it blows up half way. Both are the states
    the ordering has to survive.
    """

    def __init__(self, status: ArchiveStatus | None = None, *, unpack_fails: bool = False) -> None:
        self.packed: tuple[str, str] | None = None
        self.unpacked: tuple[str, str] | None = None
        self.inspected: list[str] = []
        self._status = status
        self._unpack_fails = unpack_fails

    def inspect(self, archive: str) -> ArchiveStatus:
        self.inspected.append(archive)
        if self._status is not None:
            return self._status
        return ArchiveStatus.COMPLETE if Path(archive).is_file() else ArchiveStatus.MISSING

    def pack(self, folder: str, slug: str) -> str:
        self.packed = (folder, slug)
        return str(Path(f"/exports/{slug}.zip"))

    def unpack(self, archive: str, destination: str) -> None:
        self.unpacked = (archive, destination)
        target = Path(destination)
        if self._unpack_fails:
            target.mkdir(parents=True, exist_ok=True)
            (target / "half-written").write_text("junk", encoding="utf-8")
            message = "the disk filled up"
            raise OSError(message)
        target.mkdir(parents=True, exist_ok=True)
        (target / "workflow.md").write_text("# steps", encoding="utf-8")


# ── export ──
def test_exporting_packs_the_workflows_own_folder(tmp_path: Path) -> None:
    archive = FakeArchive()
    written = ExportWorkflowService(FakeWorkflows(tmp_path, {"nightly-etl"}), archive).execute(
        "nightly-etl"
    )
    assert archive.packed == (str(tmp_path / "nightly-etl"), "nightly-etl")
    # Through Path, so the separator is the platform's -- the claim is that the archive's
    # own path comes back, not that it is spelled with a slash.
    assert written == str(Path("/exports/nightly-etl.zip"))


def test_exporting_an_unknown_workflow_is_refused(tmp_path: Path) -> None:
    with pytest.raises(WorkflowNotFoundError):
        ExportWorkflowService(FakeWorkflows(tmp_path), FakeArchive()).execute("ghost")


@pytest.mark.parametrize("name", ["_common", "create-workflow", "Bad Name"])
def test_exporting_a_reserved_or_invalid_name_is_refused(tmp_path: Path, name: str) -> None:
    with pytest.raises(WorkflowNameError):
        ExportWorkflowService(FakeWorkflows(tmp_path, {name}), FakeArchive()).execute(name)


# ── import ──
def _use_case(
    tmp_path: Path,
    existing: set[str] | None = None,
    archive: FakeArchive | None = None,
) -> ImportWorkflowService:
    """The use case over a real backup adapter, so the collaboration is the real one.

    Where the backup lands and what it is called are the adapter's own behaviour and are
    asserted against it directly, in ``test_filesystem_workflow_backup``; what is asserted
    here is the ordering the use case owns.
    """
    return ImportWorkflowService(
        FakeWorkflows(tmp_path / "workflows", existing),
        archive or FakeArchive(),
        FilesystemWorkflowBackupAdapter(tmp_path / "backups", lambda: _WHEN),
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


def test_replacing_displaces_the_old_workflow_and_reports_where_it_went(tmp_path: Path) -> None:
    existing = tmp_path / "workflows" / "nightly-etl"
    existing.mkdir(parents=True)
    (existing / "workflow.md").write_text("the old one", encoding="utf-8")

    result = _use_case(tmp_path, {"nightly-etl"}).execute(_an_archive(tmp_path), replace=True)

    assert result.outcome is ImportOutcome.REPLACED
    assert result.backup is not None
    # Moved, not deleted: replacing is never a one-way door.
    assert Path(result.backup, "workflow.md").read_text(encoding="utf-8") == "the old one"
    assert Path(result.path, "workflow.md").read_text(encoding="utf-8") == "# steps"


def test_a_missing_archive_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ArchiveUnreadableError):
        _use_case(tmp_path).execute(str(tmp_path / "nope.zip"))


def test_an_archive_with_no_workflow_is_refused_before_anything_moves(tmp_path: Path) -> None:
    """The defect this slot exists for: the installed workflow used to be gone by now."""
    existing = tmp_path / "workflows" / "nightly-etl"
    existing.mkdir(parents=True)
    (existing / "workflow.md").write_text("the old one", encoding="utf-8")
    archive = FakeArchive(ArchiveStatus.INCOMPLETE)

    with pytest.raises(ArchiveUnreadableError):
        _use_case(tmp_path, {"nightly-etl"}, archive).execute(_an_archive(tmp_path), replace=True)

    assert archive.unpacked is None  # never even tried
    assert (existing / "workflow.md").read_text(encoding="utf-8") == "the old one"
    assert not (tmp_path / "backups").exists()


def test_a_failed_unpack_puts_the_old_workflow_back(tmp_path: Path) -> None:
    """The other half: the archive looked fine and the disk gave out part way through."""
    existing = tmp_path / "workflows" / "nightly-etl"
    existing.mkdir(parents=True)
    (existing / "workflow.md").write_text("the old one", encoding="utf-8")

    with pytest.raises(OSError, match="the disk filled up"):
        _use_case(tmp_path, {"nightly-etl"}, FakeArchive(unpack_fails=True)).execute(
            _an_archive(tmp_path), replace=True
        )

    assert (existing / "workflow.md").read_text(encoding="utf-8") == "the old one"
    # The half-written replacement went with the failure rather than into the workflow.
    assert not (existing / "half-written").exists()


def test_an_occupied_folder_that_is_not_a_workflow_is_still_displaced(tmp_path: Path) -> None:
    """Otherwise an interrupted import's leftovers would be folded into the new one."""
    stray = tmp_path / "workflows" / "nightly-etl"
    stray.mkdir(parents=True)
    (stray / "leftover.md").write_text("residue", encoding="utf-8")

    result = _use_case(tmp_path).execute(_an_archive(tmp_path))

    assert result.outcome is ImportOutcome.REPLACED
    assert not (stray / "leftover.md").exists()


def test_an_export_timestamp_is_stripped_from_the_name(tmp_path: Path) -> None:
    # Exports are named <slug>-<date>-<time>.zip; importing one must not create a
    # workflow called "nightly-etl-20260729-153012".
    result = _use_case(tmp_path).execute(_an_archive(tmp_path, "nightly-etl-20260729-153012.zip"))
    assert result.name == "nightly-etl"


def test_an_archive_named_for_a_reserved_workflow_is_refused(tmp_path: Path) -> None:
    with pytest.raises(WorkflowNameError):
        _use_case(tmp_path).execute(_an_archive(tmp_path, "create-workflow.zip"))


# ── writing nothing on the way to a refusal ──
def test_exporting_an_unknown_workflow_writes_nothing_at_all(tmp_path: Path) -> None:
    """Against the real source, because the claim is about the disk.

    A command that fails used to leave the packaged workflows behind in the user's home —
    `gmlw workflow export ghost` printed "unknown workflow" and created two directories.
    """
    root = tmp_path / "workflows"
    use_case = ExportWorkflowService(FilesystemWorkflowSourceAdapter(root), FakeArchive())

    with pytest.raises(WorkflowNotFoundError):
        use_case.execute("ghost")

    assert not root.exists()


def test_exporting_a_reserved_name_writes_nothing_at_all(tmp_path: Path) -> None:
    root = tmp_path / "workflows"
    use_case = ExportWorkflowService(FilesystemWorkflowSourceAdapter(root), FakeArchive())

    with pytest.raises(WorkflowNameError):
        use_case.execute("create-workflow")

    assert not root.exists()


def test_importing_an_unusable_archive_writes_nothing_at_all(tmp_path: Path) -> None:
    root = tmp_path / "workflows"
    use_case = ImportWorkflowService(
        FilesystemWorkflowSourceAdapter(root),
        FakeArchive(ArchiveStatus.INCOMPLETE),
        FilesystemWorkflowBackupAdapter(tmp_path / "backups", lambda: _WHEN),
    )

    with pytest.raises(ArchiveUnreadableError):
        use_case.execute(_an_archive(tmp_path))

    assert not root.exists()
