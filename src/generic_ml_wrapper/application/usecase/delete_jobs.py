# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The DeleteJobsUseCase use case: remove whole jobs and everything recorded under them.

The coarser of the two removal grains. It is not the fold of
:class:`~generic_ml_wrapper.application.usecase.delete_sessions.DeleteSessionsService`
over the job's sessions but a superset of it: it sweeps every row keyed to the job and
both of its folders outright, so anything the job left behind that no *recorded* session
still claims goes with it. Removing a job one session at a time would leave exactly that
residue -- which is the complaint this feature answers, one level down.

Its footprint is measured the same way, from the folders and the job's rows rather than
per session, so the number a user is shown is what will actually be removed.

Every recorded job is reachable, including the authoring job. It is hidden from the
listing because its name is the system's choice rather than the user's, but hiding it
was never meant to protect it: a user who names it may remove its history like any
other's, and the workflows that history produced are not stored under it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.no_such_job_error import NoSuchJobError
from generic_ml_wrapper.application.port.inbound.delete_jobs import DeleteJobsUseCase
from generic_ml_wrapper.application.port.inbound.job_footprint import JobFootprint
from generic_ml_wrapper.application.port.outbound.artifact_purge import ArtifactPurgePort
from generic_ml_wrapper.application.port.outbound.ledger_purge import LedgerPurgePort
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.session_lock import SessionLockPort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort


class DeleteJobsService(DeleteJobsUseCase):
    """Measure and remove whole jobs."""

    def __init__(  # noqa: PLR0913, PLR0917  (the read ports it measures with, plus both purges and the lock)
        self,
        store: SessionStorePort,
        turns: PerTurnMeteringPort,
        usage: UsageStorePort,
        ledger: LedgerPurgePort,
        artifacts: ArtifactPurgePort,
        locks: SessionLockPort,
        diagnostics: DiagnosticsPort,
    ) -> None:
        """Wire the use case to the stores it measures and the purges it removes through.

        Args:
            store: Where the jobs and their sessions are read from.
            turns: Where metered turns are read from.
            usage: Where recorded session costs are read from.
            ledger: Removes the recorded rows.
            artifacts: Counts and removes the files on disk.
            diagnostics: Where a job whose files would not go is reported.
            locks: Claims each job, so none is removed while a session of it runs.
        """
        self._store = store
        self._turns = turns
        self._usage = usage
        self._ledger = ledger
        self._artifacts = artifacts
        self._locks = locks
        self._diagnostics = diagnostics

    def preview(self, jobs: Sequence[str]) -> list[JobFootprint]:
        """Report what deleting these jobs would remove, without removing it."""
        self._validate(jobs)
        return [self._footprint(job) for job in jobs]

    def execute(self, jobs: Sequence[str]) -> list[JobFootprint]:
        """Delete the jobs, their sessions, their recorded usage, and their files.

        Returns:
            One footprint per job asked for, each carrying whether it actually went. A job
            whose files could not be removed keeps its rows and comes back marked, rather
            than taking the rest of the batch down with it.

        Raises:
            JobRunningError: If any of a job's sessions has a live client.
        """
        self._validate(jobs)
        # Measured before the first removal, and returned afterwards: once the rows and
        # folders are gone there is nothing left to count.
        footprints = [self._footprint(job) for job in jobs]
        return [self._purge(footprint) for footprint in footprints]

    def _purge(self, footprint: JobFootprint) -> JobFootprint:
        """Remove one job's files and then its rows, or report that it stayed.

        Files first, for the reason the session-level delete gives: a row can be asked for
        again, a file whose row is gone cannot be found by anything.
        """
        job = footprint.job
        # One claim answers "is anything of this job running", because every running
        # session holds the job's lock shared. Held across both removals, so a session
        # cannot start into a job whose files are already going.
        with self._locks.claim_job(job):
            try:
                self._artifacts.purge_job(job)
            except OSError as error:
                self._diagnostics.warning(
                    f"job '{job}' was not deleted: its files could not be removed: {error}",
                    key="log.job_not_deleted",
                )
                return replace(footprint, removed=False)
            self._ledger.purge_job(job)
        return footprint

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
