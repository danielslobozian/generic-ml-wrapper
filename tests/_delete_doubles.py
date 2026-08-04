# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Recording doubles for the two purge ports, and a controllable session lock.

Deliberately *recording* rather than in-memory-realistic. What the delete use cases have
to get right is which purges they call and — more importantly — which they do not call
when a batch is rejected. A double that actually removed things would answer the first
question and hide the second behind an assertion about leftovers.

Not named ``test_*`` so pytest does not collect it; the concrete tests import from it, as
they do from :mod:`_conformance`.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.job_running_error import JobRunningError
from generic_ml_wrapper.application.domain.model.session_running_error import SessionRunningError
from generic_ml_wrapper.application.port.outbound.artifact_purge import (
    ArtifactCounts,
    ArtifactPurgePort,
)
from generic_ml_wrapper.application.port.outbound.ledger_purge import LedgerPurgePort
from generic_ml_wrapper.application.port.outbound.session_lock import SessionLockPort

if TYPE_CHECKING:
    from collections.abc import Generator


class FakeSessionLock(SessionLockPort):
    """A session lock whose answers a test declares, rather than a real OS lock.

    Grants every claim by default -- most tests are not about what is running -- and a
    test that *is* names the running sessions or jobs up front. It also records the
    claims made, so "the delete stopped at the running one" can be asserted directly
    rather than inferred from what was purged.
    """

    def __init__(
        self,
        running_sessions: set[str] | None = None,
        running_jobs: set[str] | None = None,
    ) -> None:
        self.running_sessions = running_sessions or set()
        self.running_jobs = running_jobs or set()
        self.claimed_sessions: list[tuple[str, str]] = []
        self.claimed_jobs: list[str] = []
        self.held_sessions: list[tuple[str, str]] = []
        self.held_jobs: list[str] = []

    @contextmanager
    def hold_session(self, job: str, session_id: str) -> Generator[None]:
        self.held_sessions.append((job, session_id))
        yield

    @contextmanager
    def hold_job(self, job: str) -> Generator[None]:
        self.held_jobs.append(job)
        yield

    @contextmanager
    def claim_session(self, job: str, session_id: str) -> Generator[None]:
        if session_id in self.running_sessions:
            raise SessionRunningError(job, session_id)
        self.claimed_sessions.append((job, session_id))
        yield

    @contextmanager
    def claim_job(self, job: str) -> Generator[None]:
        if job in self.running_jobs:
            raise JobRunningError(job)
        self.claimed_jobs.append(job)
        yield


class RecordingLedgerPurge(LedgerPurgePort):
    """Records the ledger purges asked for, in order, and performs none of them.

    ``trace`` is a log shared with the artifact purge, so a test can assert not just that
    both were asked but in which order -- which is the whole of the delete's consistency
    story and cannot be seen from two separate lists.
    """

    def __init__(self, trace: list[str] | None = None) -> None:
        self.purged_sessions: list[tuple[str, str]] = []
        self.purged_jobs: list[str] = []
        self.trace = trace if trace is not None else []

    def purge_session(self, job: str, session: str) -> None:
        self.purged_sessions.append((job, session))
        self.trace.append(f"rows:{session}")

    def purge_job(self, job: str) -> None:
        self.purged_jobs.append(job)
        self.trace.append(f"rows:{job}")


class RecordingArtifactPurge(ArtifactPurgePort):
    """Records artifact purges and answers counts a test set up in advance."""

    def __init__(self, trace: list[str] | None = None) -> None:
        self.purged_sessions: list[tuple[str, str]] = []
        self.purged_jobs: list[str] = []
        self.trace = trace if trace is not None else []
        #: Names whose file purge raises, so a test can hold one item of a batch back.
        self.unremovable: set[str] = set()
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
        self._refuse_if_unremovable(session)
        self.purged_sessions.append((job, session))
        self.trace.append(f"files:{session}")

    def purge_job(self, job: str) -> None:
        self._refuse_if_unremovable(job)
        self.purged_jobs.append(job)
        self.trace.append(f"files:{job}")

    def _refuse_if_unremovable(self, name: str) -> None:
        if name in self.unremovable:
            message = f"[Errno 13] Permission denied: {name}"
            raise OSError(message)
