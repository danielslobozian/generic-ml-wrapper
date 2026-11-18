# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for archiving the transcript folders that are no longer written to."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.application.port.outbound.transcript_archive import (
        ArchivedFolder,
        TranscriptFolder,
    )


@dataclass(frozen=True)
class ArchiveOutcome:
    """What an archiving pass did, or -- on a dry run -- would do.

    Attributes:
        archived: The folders packed, each with its archive.
        due: The folders old enough to archive; on a dry run, nothing else happened.
        changed: The folders written to while being packed, left for another time.
    """

    archived: tuple[ArchivedFolder, ...] = ()
    due: tuple[TranscriptFolder, ...] = ()
    changed: tuple[TranscriptFolder, ...] = ()


class ArchiveTranscripts(ABC):
    """Pack the transcript folders not written to for a while into archives."""

    @abstractmethod
    def execute(
        self,
        older_than_days: int,
        *,
        dry_run: bool = False,
        on_each: Callable[[TranscriptFolder, ArchivedFolder | None], None] | None = None,
    ) -> ArchiveOutcome:
        """Archive every session folder not written to for ``older_than_days`` days.

        Args:
            older_than_days: How long a folder must have gone unwritten.
            dry_run: Only say which folders are due; archive nothing.
            on_each: Told of each folder as soon as it is done -- with its archive, or
                ``None`` when it changed under the pass -- so a long pass shows progress.

        Returns:
            What was archived, what was due, and what changed under the pass.
        """
