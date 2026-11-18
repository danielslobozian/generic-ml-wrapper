# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for archiving transcript folders, and for resuming a session after it."""

from __future__ import annotations

import os
import tarfile
from typing import TYPE_CHECKING

import pytest

from generic_ml_wrapper.adapter.inbound.cli import app
from generic_ml_wrapper.adapter.outbound.store.filesystem_artifact_purge import (
    FilesystemArtifactPurge,
)
from generic_ml_wrapper.adapter.outbound.store.filesystem_transcript_archive import (
    FilesystemTranscriptArchive,
    next_call_number,
)
from generic_ml_wrapper.adapter.outbound.store.filesystem_transcript_store import (
    FilesystemTranscriptStore,
)
from generic_ml_wrapper.application.port.inbound.archive_transcripts import ArchiveOutcome
from generic_ml_wrapper.application.port.outbound.transcript import TranscriptCall
from generic_ml_wrapper.application.port.outbound.transcript_archive import (
    ArchivedFolder,
    TranscriptArchivePort,
    TranscriptFolder,
)
from generic_ml_wrapper.application.usecase.archive_transcripts import ArchiveTranscriptsUseCase

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_DAY = 86_400.0


def _record(store: FilesystemTranscriptStore, seq: int, body: bytes = b"{}") -> None:
    store.record(TranscriptCall("JOB-1", "JOB-1_001", seq, body, b"data: x\n\n", None))


def _folder(root: Path, calls: int = 2) -> Path:
    store = FilesystemTranscriptStore(root)
    for seq in range(1, calls + 1):
        _record(store, seq, f'{{"call": {seq}}}'.encode())
    return root / "JOB-1" / "JOB-1_001"


# ── the archive ──
def test_a_folder_becomes_one_checked_archive_named_by_its_calls(tmp_path: Path) -> None:
    folder = _folder(tmp_path, calls=3)
    archive = FilesystemTranscriptArchive(tmp_path)
    [listed] = archive.folders()
    assert (listed.job, listed.session, listed.files) == ("JOB-1", "JOB-1_001", 9)

    result = archive.archive(listed)

    assert result is not None
    assert result.archive == "JOB-1_001.calls-001-003.tar.xz"
    assert not folder.exists()
    with tarfile.open(tmp_path / "JOB-1" / result.archive, "r:xz") as tar:
        names = sorted(member.name for member in tar)
        stream = tar.extractfile("JOB-1_001/call_002.in.json")
        assert stream is not None
        assert stream.read() == b'{"call": 2}'
    assert names[0] == "JOB-1_001/call_001.in.json"
    assert len(names) == 9
    assert archive.folders() == []  # nothing left to archive


def test_a_folder_written_to_while_packed_is_left_as_it_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = _folder(tmp_path)
    archive = FilesystemTranscriptArchive(tmp_path)
    [listed] = archive.folders()
    real_open = tarfile.open

    def open_then_write(*args: object, **kwargs: object) -> tarfile.TarFile:
        (folder / "call_003.in.json").write_bytes(b"{}")  # a call lands mid-pack
        monkeypatch.setattr(tarfile, "open", real_open)
        return real_open(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(tarfile, "open", open_then_write)
    assert archive.archive(listed) is None
    assert folder.is_dir()
    assert not list((tmp_path / "JOB-1").glob("*.tar.xz*"))  # no archive, no leftover


# ── resuming ──
def test_a_resumed_session_numbers_on_after_its_archived_calls(tmp_path: Path) -> None:
    _folder(tmp_path, calls=2)
    archive = FilesystemTranscriptArchive(tmp_path)
    archive.archive(archive.folders()[0])

    resumed = FilesystemTranscriptStore(tmp_path)  # a new run: the relay counts from 1
    _record(resumed, 1)

    folder = tmp_path / "JOB-1" / "JOB-1_001"
    assert sorted(path.name for path in folder.iterdir())[0] == "call_003.in.json"
    [again] = archive.folders()
    result = archive.archive(again)
    assert result is not None
    assert result.archive == "JOB-1_001.calls-003-003.tar.xz"
    assert next_call_number(tmp_path / "JOB-1", "JOB-1_001") == 4


def test_a_resumed_session_never_writes_over_its_earlier_calls(tmp_path: Path) -> None:
    folder = _folder(tmp_path, calls=2)
    _record(FilesystemTranscriptStore(tmp_path), 1, b'{"run": 2}')  # a second run's first
    assert (folder / "call_001.in.json").read_bytes() == b'{"call": 1}'
    assert (folder / "call_003.in.json").read_bytes() == b'{"run": 2}'


def test_deleting_a_session_removes_its_archives_too(tmp_path: Path) -> None:
    _folder(tmp_path)
    archive = FilesystemTranscriptArchive(tmp_path)
    archive.archive(archive.folders()[0])
    purge = FilesystemArtifactPurge(tmp_path / "contexts", tmp_path)
    assert purge.counts_for_session("JOB-1", "JOB-1_001").transcript_calls == 1
    purge.purge_session("JOB-1", "JOB-1_001")
    assert list((tmp_path / "JOB-1").iterdir()) == []


# ── the use case ──
class _FakeArchive(TranscriptArchivePort):
    def __init__(self, folders: list[TranscriptFolder], changed: str = "") -> None:
        self._folders = folders
        self._changed = changed
        self.packed: list[str] = []

    def folders(self) -> list[TranscriptFolder]:
        return self._folders

    def archive(self, folder: TranscriptFolder) -> ArchivedFolder | None:
        self.packed.append(folder.session)
        return None if folder.session == self._changed else ArchivedFolder(folder, "a", 1)


def _aged(session: str, days: float) -> TranscriptFolder:
    return TranscriptFolder("J", session, 3, 1000, 100 * _DAY - days * _DAY)


def test_only_folders_unwritten_for_long_enough_are_archived() -> None:
    fake = _FakeArchive([_aged("old", 8), _aged("new", 2), _aged("changing", 9)], "changing")
    seen: list[tuple[str, bool]] = []
    outcome = ArchiveTranscriptsUseCase(fake, clock=lambda: 100 * _DAY).execute(
        7, on_each=lambda folder, done: seen.append((folder.session, done is not None))
    )
    assert fake.packed == ["old", "changing"]
    assert [item.folder.session for item in outcome.archived] == ["old"]
    assert [folder.session for folder in outcome.changed] == ["changing"]
    assert seen == [("old", True), ("changing", False)]


def test_a_dry_run_archives_nothing() -> None:
    fake = _FakeArchive([_aged("old", 8)])
    outcome = ArchiveTranscriptsUseCase(fake, clock=lambda: 100 * _DAY).execute(7, dry_run=True)
    assert fake.packed == []
    assert [folder.session for folder in outcome.due] == ["old"]


# ── the command ──
def test_the_command_reports_each_folder_and_the_total(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = TranscriptFolder("J", "J_001", 9, 8_900_000, 0.0)
    archived = ArchivedFolder(folder, "J_001.calls-001-003.tar.xz", 193_000)

    class _Fake(ArchiveTranscriptsUseCase):
        def __init__(self) -> None:
            pass

        def execute(
            self,
            older_than_days: int,
            *,
            dry_run: bool = False,
            on_each: Callable[[TranscriptFolder, ArchivedFolder | None], None] | None = None,
        ) -> ArchiveOutcome:
            assert older_than_days == 3
            if dry_run:
                return ArchiveOutcome(due=(folder,))
            if on_each is not None:
                on_each(folder, archived)
            return ArchiveOutcome(archived=(archived,), due=(folder,))

    monkeypatch.setattr(app, "build_archive_transcripts", _Fake)
    assert app.main(["transcripts", "archive", "--older-than", "3"]) == 0
    out = capsys.readouterr().out
    assert "J/J_001  8.9 MB → 193.0 kB" in out
    assert "1 folder(s) archived: 8.9 MB → 193.0 kB" in out
    assert app.main(["transcripts", "archive", "--older-than", "3", "--dry-run"]) == 0
    assert "1 folder(s) to archive, 8.9 MB in all" in capsys.readouterr().out


def test_a_folders_last_write_is_its_newest_file(tmp_path: Path) -> None:
    folder = _folder(tmp_path)
    stamp = 1_000_000_000
    for path in folder.iterdir():
        os.utime(path, (stamp, stamp))
    archive = FilesystemTranscriptArchive(tmp_path)
    [listed] = archive.folders()
    assert listed.last_written == stamp
    assert archive.archive(listed) is not None
