# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the files a job or session leaves behind."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactCounts:
    """How many files a job or session holds outside the ledger.

    Attributes:
        contexts: Compiled-context files (one per session that launched fresh).
        transcript_calls: Recorded transcript files (three per metered call, when the
            opt-in transcript is on; ``0`` when it never was).
    """

    contexts: int
    transcript_calls: int

    def __add__(self, other: ArtifactCounts) -> ArtifactCounts:
        """Sum two counts, so a job's footprint folds over its sessions'."""
        return ArtifactCounts(
            contexts=self.contexts + other.contexts,
            transcript_calls=self.transcript_calls + other.transcript_calls,
        )


class ArtifactPurgePort(ABC):
    """Count and remove the on-disk artifacts of a session or a job.

    Unlike the recorded rows, these files have no reader port to count them through:
    they are written straight to disk by the context writer and the transcript store.
    So this port both counts and removes -- the count is what a user is shown before
    confirming, and it can only be taken here.
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
        """

    @abstractmethod
    def purge_job(self, job: str) -> None:
        """Remove a job's whole context and transcript folders.

        Args:
            job: The job to remove.
        """
