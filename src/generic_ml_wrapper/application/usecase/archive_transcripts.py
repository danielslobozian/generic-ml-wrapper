# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ArchiveTranscripts use case: pack the transcript folders no longer written to."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.archive_transcripts import (
    ArchiveOutcome,
    ArchiveTranscripts,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.application.port.outbound.transcript_archive import (
        ArchivedFolder,
        TranscriptArchivePort,
        TranscriptFolder,
    )

_DAY = 86_400


class ArchiveTranscriptsUseCase(ArchiveTranscripts):
    """Choose the folders old enough, then archive them one at a time."""

    def __init__(self, archive: TranscriptArchivePort, clock: Callable[[], float]) -> None:
        """Wire the use case to the transcript archive and a clock.

        Args:
            archive: Lists the session folders and packs one.
            clock: The current epoch seconds; injectable so tests are deterministic.
        """
        self._archive = archive
        self._clock = clock

    def execute(
        self,
        older_than_days: int,
        *,
        dry_run: bool = False,
        on_each: Callable[[TranscriptFolder, ArchivedFolder | None], None] | None = None,
    ) -> ArchiveOutcome:
        """Archive every session folder not written to for ``older_than_days`` days."""
        cutoff = self._clock() - older_than_days * _DAY
        due = tuple(folder for folder in self._archive.folders() if folder.last_written < cutoff)
        if dry_run:
            return ArchiveOutcome(due=due)
        archived: list[ArchivedFolder] = []
        changed: list[TranscriptFolder] = []
        for folder in due:
            result = self._archive.archive(folder)
            if on_each is not None:
                on_each(folder, result)
            if result is None:
                changed.append(folder)
            else:
                archived.append(result)
        return ArchiveOutcome(archived=tuple(archived), due=due, changed=tuple(changed))
