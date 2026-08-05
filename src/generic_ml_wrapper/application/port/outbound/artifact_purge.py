# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the files a job or session leaves behind."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.outbound.artifact_counts import ArtifactCounts


class ArtifactPurgePort(ABC):
    """Count and remove the on-disk artifacts of a session or a job.

    Unlike the recorded rows, these files have no reader port to count them through:
    they are written straight to disk by the context writer and the transcript store.
    So this port both counts and removes -- the count is what a user is shown before
    confirming, and it can only be taken here.

    **Removal reports failure.** A caller deletes these files *before* the rows that name
    them, so that a delete which does not finish leaves a session that still lists and
    still works, and can simply be asked for again. That only holds if an implementation
    says when it did not remove something: silently keeping the files while the rows go
    would strand them where nothing can find them. Finding nothing to remove is not a
    failure -- transcripts are opt-in.
    """

    @abstractmethod
    def counts_for_session(self, job: str, session: str) -> ArtifactCounts:
        """Return what one session holds on disk (zeroes when it holds nothing).

        Args:
            job: The job the session belongs to.
            session: The session's ``<job>_NNN`` id.
        """

    @abstractmethod
    def counts_for_job(self, job: str) -> ArtifactCounts:
        """Return what a whole job holds on disk (zeroes when it holds nothing).

        Args:
            job: The job to measure.
        """

    @abstractmethod
    def purge_session(self, job: str, session: str) -> None:
        """Remove one session's compiled context and transcript folder.

        The job's folders are left in place, even when this empties them: they are
        removed by :meth:`purge_job`, so a session delete never disturbs its siblings.

        Args:
            job: The job the session belongs to.
            session: The session's ``<job>_NNN`` id.

        Raises:
            OSError: If something that is there cannot be removed.
        """

    @abstractmethod
    def purge_job(self, job: str) -> None:
        """Remove a job's whole context and transcript folders.

        Args:
            job: The job to remove.

        Raises:
            OSError: If something that is there cannot be removed.
        """
