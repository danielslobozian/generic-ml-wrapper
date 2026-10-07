# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Recording doubles for the two purge ports.

Deliberately *recording* rather than in-memory-realistic. What the delete use cases have
to get right is which purges they call and — more importantly — which they do not call
when a batch is rejected. A double that actually removed things would answer the first
question and hide the second behind an assertion about leftovers.

Not named ``test_*`` so pytest does not collect it; the concrete tests import from it, as
they do from :mod:`_conformance`.
"""

from __future__ import annotations

from generic_ml_wrapper.application.port.outbound.artifact_purge import (
    ArtifactCounts,
    ArtifactPurgePort,
)
from generic_ml_wrapper.application.port.outbound.ledger_purge import LedgerPurgePort


class RecordingLedgerPurge(LedgerPurgePort):
    """Records the ledger purges asked for, in order, and performs none of them."""

    def __init__(self, calls: list[str] | None = None) -> None:
        self.purged_sessions: list[tuple[str, str]] = []
        self.purged_jobs: list[str] = []
        self._calls = calls if calls is not None else []

    def purge_session(self, job: str, session: str) -> None:
        self._calls.append(f"rows {session}")
        self.purged_sessions.append((job, session))

    def purge_job(self, job: str) -> None:
        self._calls.append(f"rows {job}")
        self.purged_jobs.append(job)


class RecordingArtifactPurge(ArtifactPurgePort):
    """Records artifact purges and answers counts a test set up in advance.

    ``stuck`` names the sessions and jobs whose files will not go: purging one raises
    ``OSError``, as a permission error or a read-only mount would. ``calls`` is a log
    shared with a :class:`RecordingLedgerPurge`, so a test can see which went first.
    """

    def __init__(self, calls: list[str] | None = None, stuck: frozenset[str] = frozenset()) -> None:
        self.purged_sessions: list[tuple[str, str]] = []
        self.purged_jobs: list[str] = []
        self._calls = calls if calls is not None else []
        self._stuck = stuck
        self._session_counts: dict[tuple[str, str], ArtifactCounts] = {}
        self._job_counts: dict[str, ArtifactCounts] = {}

    def set_session_counts(
        self, job: str, session: str, *, contexts: int, transcript_calls: int
    ) -> None:
        """Declare what one session is holding on disk."""
        self._session_counts[(job, session)] = ArtifactCounts(contexts, transcript_calls)

    def set_job_counts(self, job: str, *, contexts: int, transcript_calls: int) -> None:
        """Declare what a whole job is holding on disk."""
        self._job_counts[job] = ArtifactCounts(contexts, transcript_calls)

    def counts_for_session(self, job: str, session: str) -> ArtifactCounts:
        return self._session_counts.get((job, session), ArtifactCounts(0, 0))

    def counts_for_job(self, job: str) -> ArtifactCounts:
        return self._job_counts.get(job, ArtifactCounts(0, 0))

    def purge_session(self, job: str, session: str) -> None:
        if session in self._stuck:
            raise PermissionError(f"cannot remove {session}")
        self._calls.append(f"files {session}")
        self.purged_sessions.append((job, session))

    def purge_job(self, job: str) -> None:
        if job in self._stuck:
            raise PermissionError(f"cannot remove {job}")
        self._calls.append(f"files {job}")
        self.purged_jobs.append(job)
