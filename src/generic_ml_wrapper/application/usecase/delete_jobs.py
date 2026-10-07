# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The DeleteJobs use case: remove whole jobs and everything recorded under them.

The coarser of the two removal grains. It is not the fold of
:class:`~generic_ml_wrapper.application.usecase.delete_sessions.DeleteSessionsUseCase`
over the job's sessions but a superset of it: it sweeps every row keyed to the job and
both of its folders outright, so anything the job left behind that no *recorded* session
still claims goes with it. Removing a job one session at a time would leave exactly that
residue -- which is the complaint this feature answers, one level down.

Its footprint is measured the same way, from the folders and the job's rows rather than
per session, so the number a user is shown is what will actually be removed.

Only jobs the injected store can see are reachable. That store is scoped to ``kind``, so
wiring it to the ``work`` store makes authoring jobs unreachable here for the same reason
they are absent from ``gmlw jobs`` -- no extra guard to remember.
"""

from __future__ import annotations

from collections.abc import Sequence

from generic_ml_wrapper.application.port.inbound.delete_jobs import DeleteJobs, JobFootprint
from generic_ml_wrapper.application.port.inbound.delete_sessions import NoSuchJobError
from generic_ml_wrapper.application.port.outbound.artifact_purge import ArtifactPurgePort
from generic_ml_wrapper.application.port.outbound.ledger_purge import LedgerPurgePort
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort


class DeleteJobsUseCase(DeleteJobs):
    """Measure and remove whole jobs."""

    def __init__(
        self,
        store: SessionStorePort,
        turns: PerTurnMeteringPort,
        usage: UsageStorePort,
        ledger: LedgerPurgePort,
        artifacts: ArtifactPurgePort,
    ) -> None:
        """Wire the use case to the stores it measures and the purges it removes through.

        Args:
            store: Where the jobs and their sessions are read from -- and, being
                ``kind``-scoped, which jobs are reachable at all.
            turns: Where metered turns are read from.
            usage: Where recorded session costs are read from.
            ledger: Removes the recorded rows.
            artifacts: Counts and removes the files on disk.
        """
        self._store = store
        self._turns = turns
        self._usage = usage
        self._ledger = ledger
        self._artifacts = artifacts

    def preview(self, jobs: Sequence[str]) -> list[JobFootprint]:
        """Report what deleting these jobs would remove, without removing it."""
        self._validate(jobs)
        return [self._footprint(job) for job in jobs]

    def execute(self, jobs: Sequence[str]) -> list[JobFootprint]:
        """Delete the jobs, their sessions, their recorded usage, and their files."""
        self._validate(jobs)
        # Measured before the first removal, and returned afterwards: once the rows and
        # folders are gone there is nothing left to count.
        footprints = [self._footprint(job) for job in jobs]
        for job in jobs:
            self._ledger.purge_job(job)
            self._artifacts.purge_job(job)
        return footprints

    def _validate(self, jobs: Sequence[str]) -> None:
        """Reject the whole batch unless every job in it has recorded activity.

        Raises:
            NoSuchJobError: If any job has no recorded activity.
        """
        known = set(self._store.jobs())
        for job in jobs:
            if job not in known:
                raise NoSuchJobError("error.job.not_found", job=job)

    def _footprint(self, job: str) -> JobFootprint:
        """Measure a job from its rows and its folders."""
        counts = self._artifacts.counts_for_job(job)
        return JobFootprint(
            job=job,
            sessions=len(self._store.ids_for_job(job)),
            turns=len(self._turns.turns_for_job(job)),
            cost_usd=sum(self._usage.session_costs(job).values()),
            contexts=counts.contexts,
            transcript_calls=counts.transcript_calls,
        )
