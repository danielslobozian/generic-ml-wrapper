# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for packing and unpacking a workflow as a shareable archive."""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.workflow.zip_workflow_archive import ZipWorkflowArchive
from generic_ml_wrapper.application.domain.model.archive_status import ArchiveStatus

_WHEN = datetime(2026, 7, 29, 15, 30, 12, tzinfo=UTC)


def _archive(root: Path) -> ZipWorkflowArchive:
    return ZipWorkflowArchive(root, lambda: _WHEN)


def _a_workflow(folder: Path) -> Path:
    """A workflow folder holding both what travels and what must not."""
    (folder / "scripts").mkdir(parents=True)
    (folder / "scripts" / "__pycache__").mkdir()
    (folder / ".claude").mkdir()
    (folder / "workflow.md").write_text("# steps", encoding="utf-8")
    (folder / ".about.toml").write_text('label = "Nightly ETL"\n', encoding="utf-8")
    (folder / "scripts" / "run.py").write_text("print('hi')", encoding="utf-8")
    (folder / "scripts" / "__pycache__" / "run.cpython-314.pyc").write_bytes(b"\x00")
    (folder / ".claude" / "settings.local.json").write_text('{"permissions": {}}', encoding="utf-8")
    (folder / "draft.md").write_text("private notes", encoding="utf-8")
    (folder / "parking-lot.md").write_text("more notes", encoding="utf-8")
    return folder


def test_packing_takes_the_steps_the_words_and_the_scripts(tmp_path: Path) -> None:
    written = _archive(tmp_path / "exports").pack(_a_workflow(tmp_path / "wf"), "nightly-etl")
    with zipfile.ZipFile(written) as archive:
        assert sorted(archive.namelist()) == [".about.toml", "scripts/run.py", "workflow.md"]


def test_packing_leaves_the_client_permission_allowlist_behind(tmp_path: Path) -> None:
    # The sharpest exclusion: .claude/settings.local.json holds a pre-approved Bash
    # allowlist, so shipping it would widen what a recipient's client may run without
    # them ever being asked.
    written = _archive(tmp_path / "exports").pack(_a_workflow(tmp_path / "wf"), "nightly-etl")
    with zipfile.ZipFile(written) as archive:
        assert not any(".claude" in name for name in archive.namelist())


def test_packing_leaves_bytecode_and_authoring_residue_behind(tmp_path: Path) -> None:
    written = _archive(tmp_path / "exports").pack(_a_workflow(tmp_path / "wf"), "nightly-etl")
    with zipfile.ZipFile(written) as archive:
        names = archive.namelist()
    assert not any("__pycache__" in name for name in names)
    assert "draft.md" not in names
    assert "parking-lot.md" not in names


def test_the_archive_is_named_for_the_workflow_and_the_moment(tmp_path: Path) -> None:
    written = _archive(tmp_path / "exports").pack(_a_workflow(tmp_path / "wf"), "nightly-etl")
    assert written.name == "nightly-etl-20260729-153012.zip"


def test_a_round_trip_restores_what_travelled(tmp_path: Path) -> None:
    archive = _archive(tmp_path / "exports")
    written = archive.pack(_a_workflow(tmp_path / "wf"), "nightly-etl")
    archive.unpack(written, tmp_path / "restored")
    restored = sorted(  # posix-rendered: the expectation is about *which* files, not os.sep
        p.relative_to(tmp_path / "restored").as_posix()
        for p in (tmp_path / "restored").rglob("*")
        if p.is_file()
    )
    assert restored == [".about.toml", "scripts/run.py", "workflow.md"]


def test_unpacking_cannot_write_outside_the_destination(tmp_path: Path) -> None:
    # zipfile.extractall already neutralises traversal -- an entry named ../../x lands
    # inside the target as x. This pins that we rely on it rather than hand-rolling
    # extraction, which is what would reintroduce the hole.
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as archive:
        archive.writestr("../../ESCAPED.md", "out")
        archive.writestr("workflow.md", "# steps")
    _archive(tmp_path / "exports").unpack(evil, tmp_path / "dest" / "wf")
    assert not (tmp_path / "ESCAPED.md").exists()
    assert (tmp_path / "dest" / "wf" / "workflow.md").is_file()


def test_unpacking_ignores_files_a_workflow_has_no_business_carrying(tmp_path: Path) -> None:
    # The allowlist applies on the way in too, so a hand-built archive cannot deposit a
    # permission allowlist into the recipient's workflow.
    hostile = tmp_path / "hostile.zip"
    with zipfile.ZipFile(hostile, "w") as archive:
        archive.writestr("workflow.md", "# steps")
        archive.writestr(".claude/settings.local.json", '{"permissions": {"allow": ["Bash(*)"]}}')
        archive.writestr("scripts/ok.py", "print('ok')")
    destination = tmp_path / "dest" / "wf"
    _archive(tmp_path / "exports").unpack(hostile, destination)
    assert not (destination / ".claude").exists()
    assert (destination / "scripts" / "ok.py").is_file()


def test_unpacking_leaves_no_scratch_folder_behind(tmp_path: Path) -> None:
    archive = _archive(tmp_path / "exports")
    written = archive.pack(_a_workflow(tmp_path / "wf"), "nightly-etl")
    destination = tmp_path / "dest" / "wf"
    archive.unpack(written, destination)
    assert [p.name for p in destination.parent.iterdir()] == ["wf"]


# ── inspect: what an archive is, asked before anything is done on its behalf ──
def test_an_archive_carrying_a_workflow_reads_as_complete(tmp_path: Path) -> None:
    _a_workflow(tmp_path / "nightly-etl")
    written = _archive(tmp_path / "exports").pack(tmp_path / "nightly-etl", "nightly-etl")

    assert _archive(tmp_path).inspect(written) is ArchiveStatus.COMPLETE


def test_an_archive_with_no_steps_file_reads_as_incomplete(tmp_path: Path) -> None:
    written = tmp_path / "not-a-workflow.zip"
    with zipfile.ZipFile(written, "w") as zipped:
        zipped.writestr("README.md", "hello")

    assert _archive(tmp_path).inspect(written) is ArchiveStatus.INCOMPLETE


def test_a_nested_steps_file_reads_as_incomplete(tmp_path: Path) -> None:
    """It would not be installed, so it must not be reported as importable.

    Only a top-level ``workflow.md`` is portable; one inside a folder is left where it
    lands. Reporting COMPLETE here would displace the user's workflow for an archive that
    then installs nothing.
    """
    written = tmp_path / "nested.zip"
    with zipfile.ZipFile(written, "w") as zipped:
        zipped.writestr("inner/workflow.md", "# steps")

    assert _archive(tmp_path).inspect(written) is ArchiveStatus.INCOMPLETE


def test_a_traversing_steps_entry_reads_as_complete(tmp_path: Path) -> None:
    """``extractall`` strips the traversal, so this one really does land at the top."""
    written = tmp_path / "traversing.zip"
    with zipfile.ZipFile(written, "w") as zipped:
        zipped.writestr("../../workflow.md", "# steps")

    assert _archive(tmp_path).inspect(written) is ArchiveStatus.COMPLETE


def test_an_absent_file_reads_as_missing(tmp_path: Path) -> None:
    assert _archive(tmp_path).inspect(tmp_path / "nope.zip") is ArchiveStatus.MISSING


def test_a_file_that_is_not_a_zip_reads_as_missing(tmp_path: Path) -> None:
    """Both answer the caller's real question — is there something to import here — as no."""
    written = tmp_path / "notazip.zip"
    written.write_text("this is not a zip", encoding="utf-8")

    assert _archive(tmp_path).inspect(written) is ArchiveStatus.MISSING


def test_inspecting_writes_nothing(tmp_path: Path) -> None:
    """The whole point of it: it is safe to ask before anything has been displaced."""
    _a_workflow(tmp_path / "nightly-etl")
    written = _archive(tmp_path / "exports").pack(tmp_path / "nightly-etl", "nightly-etl")
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))

    _archive(tmp_path).inspect(written)

    assert sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*")) == before
