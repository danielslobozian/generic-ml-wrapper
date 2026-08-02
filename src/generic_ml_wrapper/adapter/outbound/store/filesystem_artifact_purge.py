# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``ArtifactPurgePort``: the compiled contexts and transcripts on disk.

Two roots, mirroring the two writers::

    <contexts>/<job>/<session>.context.md          context_file.write
    <transcripts>/<job>/<session>/call_NNN.*       FilesystemTranscriptStore.record

The transcript root is configurable (``[transcript] root``), so it is injected rather
than read from ``paths`` -- deleting from the default root while the user records into
their own would leave exactly the files they wanted gone.

Every path here is built from a ``JobId``-validated job and a ``<job>_NNN`` session id,
both single safe path segments, so no argument can escape its root. A missing folder is
not an error: transcripts are opt-in, and a job that never had them simply counts zero.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.artifact_purge import (
    ArtifactCounts,
    ArtifactPurgePort,
)

if TYPE_CHECKING:
    from pathlib import Path


class FilesystemArtifactPurge(ArtifactPurgePort):
    """Count and remove a session's or a job's files under the two artifact roots."""

    def __init__(self, contexts_root: Path, transcripts_root: Path) -> None:
        """Bind the purge to the roots the two writers use.

        Args:
            contexts_root: Where ``<job>/<session>.context.md`` files are written.
            transcripts_root: Where ``<job>/<session>/`` transcript folders are written
                (the configured root when ``[transcript] root`` is set).
        """
        self._contexts = contexts_root
        self._transcripts = transcripts_root

    def counts_for_session(self, job: str, session: str) -> ArtifactCounts:
        """Return one session's context file (0 or 1) and its transcript file count."""
        return ArtifactCounts(
            contexts=int(self._context_file(job, session).is_file()),
            transcript_calls=_files_in(self._transcripts / job / session),
        )

    def counts_for_job(self, job: str) -> ArtifactCounts:
        """Return the whole job's context and transcript file counts."""
        return ArtifactCounts(
            contexts=_files_in(self._contexts / job),
            transcript_calls=_files_in(self._transcripts / job),
        )

    def purge_session(self, job: str, session: str) -> None:
        """Remove one session's context file and transcript folder."""
        self._context_file(job, session).unlink(missing_ok=True)
        shutil.rmtree(self._transcripts / job / session, ignore_errors=True)

    def purge_job(self, job: str) -> None:
        """Remove the job's whole context and transcript folders."""
        shutil.rmtree(self._contexts / job, ignore_errors=True)
        shutil.rmtree(self._transcripts / job, ignore_errors=True)

    def _context_file(self, job: str, session: str) -> Path:
        return self._contexts / job / f"{session}.context.md"


def _files_in(directory: Path) -> int:
    """Count the files under ``directory``, recursively; ``0`` if it is not there."""
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.rglob("*") if path.is_file())
