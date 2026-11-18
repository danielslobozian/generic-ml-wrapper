# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``TranscriptArchivePort``: a session's transcript folder, packed as tar.xz.

A session's calls live in ``<root>/<job>/<session>/call_NNN.*`` until they are archived;
then they live in ``<root>/<job>/<session>.calls-<first>-<last>.tar.xz`` beside where the
folder was. An archive is never reopened: a resumed session writes its next calls into a
fresh folder, numbered on from the last archive (see
:func:`next_call_number`), and that folder becomes an archive of its own later -- the
way logrotate never reopens a rotated file.

tar.xz rather than zip because each call's request repeats the whole conversation so
far: one compressed stream over the folder finds that repetition, a zip of separately
compressed files cannot (about forty times smaller against under three, on a real
session).
"""

from __future__ import annotations

import hashlib
import re
import shutil
import tarfile
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.transcript_archive import (
    ArchivedFolder,
    TranscriptArchivePort,
    TranscriptFolder,
)

if TYPE_CHECKING:
    from pathlib import Path

#: ``call_NNN.<kind>``: one call's file in a session folder.
_CALL_FILE = re.compile(r"^call_(\d+)\.")
#: ``<session>.calls-<first>-<last>.tar.xz``: one archive of a session's calls.
_ARCHIVE = re.compile(r"^(?P<session>.+)\.calls-(?P<first>\d+)-(?P<last>\d+)\.tar\.xz$")
_PARTIAL = ".partial"
_CHUNK = 1 << 20


def archive_name(session: str, first: int, last: int) -> str:
    """The file name of the archive holding calls ``first`` to ``last`` of a session."""
    return f"{session}.calls-{first:03d}-{last:03d}.tar.xz"


def archives_of(job_dir: Path, session: str) -> list[Path]:
    """A session's archives in its job folder, oldest calls first."""
    if not job_dir.is_dir():
        return []
    found: list[tuple[int, Path]] = []
    for path in job_dir.iterdir():
        match = _ARCHIVE.match(path.name)
        if match is not None and match["session"] == session:
            found.append((int(match["first"]), path))
    return [path for _, path in sorted(found)]


def next_call_number(job_dir: Path, session: str) -> int:
    """The number the session's next call takes: one past any call already kept.

    Both places a call can be are counted -- the session's folder and the names of its
    archives -- so a resumed session never writes over a call an earlier run recorded.
    """
    numbers = [
        int(match[1])
        for path in _files(job_dir / session)
        if (match := _CALL_FILE.match(path.name)) is not None
    ]
    numbers += [
        int(match["last"])
        for path in archives_of(job_dir, session)
        if (match := _ARCHIVE.match(path.name)) is not None
    ]
    return max(numbers, default=0) + 1


class FilesystemTranscriptArchive(TranscriptArchivePort):
    """List the session folders under the transcript root, and pack one into tar.xz."""

    def __init__(self, root: Path) -> None:
        """Bind the archive to the transcript root (the configured one, else the default)."""
        self._root = root

    def folders(self) -> list[TranscriptFolder]:
        """Every session folder that still holds calls, with its size and last write."""
        found: list[TranscriptFolder] = []
        if not self._root.is_dir():
            return found
        for job_dir in sorted(path for path in self._root.iterdir() if path.is_dir()):
            for folder in sorted(path for path in job_dir.iterdir() if path.is_dir()):
                files = _files(folder)
                if files:
                    stats = [path.stat() for path in files]
                    found.append(
                        TranscriptFolder(
                            job=job_dir.name,
                            session=folder.name,
                            files=len(files),
                            size=sum(stat.st_size for stat in stats),
                            last_written=max(stat.st_mtime for stat in stats),
                        )
                    )
        return found

    def archive(self, folder: TranscriptFolder) -> ArchivedFolder | None:
        """Pack the folder into its archive, check the archive, then remove the folder.

        The archive is written under a temporary name and renamed only once read back
        whole: every file in it, byte for byte. A folder written to while it was being
        packed is left as it was (``None``), to be archived another time.

        Raises:
            OSError: If the archive cannot be written or the folder cannot be removed.
        """
        directory = self._root / folder.job / folder.session
        before = _snapshot(directory)
        numbers = [
            int(match[1]) for name in before if (match := _CALL_FILE.match(name)) is not None
        ]
        if not numbers:
            return None
        target = directory.parent / archive_name(folder.session, min(numbers), max(numbers))
        partial = target.with_name(target.name + _PARTIAL)
        with tarfile.open(partial, "w:xz") as tar:
            for name in sorted(before):
                tar.add(directory / name, arcname=f"{folder.session}/{name}")
        if _snapshot(directory) != before or not _matches(partial, directory, folder.session):
            partial.unlink()
            return None
        partial.rename(target)
        shutil.rmtree(directory)
        return ArchivedFolder(folder, target.name, target.stat().st_size)


def _files(directory: Path) -> list[Path]:
    """The files directly in ``directory``; none when it is not there."""
    if not directory.is_dir():
        return []
    return [path for path in directory.iterdir() if path.is_file()]


def _snapshot(directory: Path) -> dict[str, tuple[int, int]]:
    """Each file's ``(size, mtime_ns)``, by name: what a change would show in."""
    return {path.name: (path.stat().st_size, path.stat().st_mtime_ns) for path in _files(directory)}


def _matches(archive: Path, directory: Path, session: str) -> bool:
    """Whether the archive holds exactly the folder's files, with the same bytes."""
    expected = {path.name: _digest_file(path) for path in _files(directory)}
    found: dict[str, str] = {}
    with tarfile.open(archive, "r:xz") as tar:
        for member in tar:
            stream = tar.extractfile(member)
            if stream is None or not member.name.startswith(f"{session}/"):
                return False
            digest = hashlib.sha256()
            while chunk := stream.read(_CHUNK):
                digest.update(chunk)
            found[member.name.removeprefix(f"{session}/")] = digest.hexdigest()
    return found == expected


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()
