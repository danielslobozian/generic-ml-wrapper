# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for archiving transcript folders that are no longer written to."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptFolder:
    """A session's folder of recorded calls.

    Attributes:
        job: The job it belongs to.
        session: The session it belongs to.
        files: How many files it holds.
        size: Their total size, in bytes.
        last_written: When a file in it was last written (epoch seconds).
    """

    job: str
    session: str
    files: int
    size: int
    last_written: float


@dataclass(frozen=True)
class ArchivedFolder:
    """A folder packed into an archive.

    Attributes:
        folder: The folder as it was.
        archive: The archive's file name, beside where the folder was.
        archive_size: The archive's size, in bytes.
    """

    folder: TranscriptFolder
    archive: str
    archive_size: int


class TranscriptArchivePort(ABC):
    """List the transcript's session folders, and pack one into an archive."""

    @abstractmethod
    def folders(self) -> list[TranscriptFolder]:
        """Every session folder that still holds calls."""

    @abstractmethod
    def archive(self, folder: TranscriptFolder) -> ArchivedFolder | None:
        """Pack the folder into an archive and remove it, once the archive is checked.

        Returns:
            The archive, or ``None`` when the folder changed while it was being packed
            and was left as it was.

        Raises:
            OSError: If the archive cannot be written or the folder cannot be removed.
        """
