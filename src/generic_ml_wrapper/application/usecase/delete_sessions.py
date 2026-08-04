# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The DeleteSessions use case: remove sessions, their usage, and their files.

The session is the finer of the two removal grains. It is deliberately surgical -- it
touches only the rows and files keyed to the sessions named, and leaves the job row and
the job's folders standing, however empty that makes them. Deleting a whole job is the
coarser grain and sweeps the folders outright (see :mod:`..delete_jobs`).

Nothing here renumbers: ``next_session_id`` mints one past the highest existing suffix
precisely so gaps are harmless, which is what makes deleting a session in the middle of
a job safe.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.delete_sessions import (
    DeleteSessions,
    NoSuchJobError,
    NoSuchSessionError,
    SessionFootprint,
)
from generic_ml_wrapper.application.port.outbound.artifact_purge import ArtifactPurgePort
from generic_ml_wrapper.application.port.outbound.ledger_purge import LedgerPurgePort
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.session_lock import SessionLockPort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.service.diagnostics import Diagnostics
    from generic_ml_wrapper.application.domain.service.localizer import Localizer


class DeleteSessionsUseCase(DeleteSessions):
    """Measure and remove a job's sessions."""

    def __init__(  # noqa: PLR0913, PLR0917  (the read ports it measures with, plus both purges and the lock)
        self,
        store: SessionStorePort,
        turns: PerTurnMeteringPort,
        usage: UsageStorePort,
        ledger: LedgerPurgePort,
        artifacts: ArtifactPurgePort,
        locks: SessionLockPort,
        diagnostics: Diagnostics,
        localizer: Localizer,
    ) -> None:
        """Wire the use case to the stores it measures and the purges it removes through.

        The three read ports are the ones the listing commands already use, so a preview
        counts exactly what ``gmlw sessions`` reports -- no second, drifting definition
        of what a session holds.

        Args:
            store: Where the job's sessions are read from.
            turns: Where metered turns are read from.
            usage: Where recorded session costs are read from.
            ledger: Removes the recorded rows.
            artifacts: Counts and removes the files on disk.
            diagnostics: Where a session whose files would not go is reported.
            localizer: Renders that report in the language the wrapper is speaking.
            locks: Claims each session, so none is removed while its client runs.
        """
        self._store = store
        self._turns = turns
        self._usage = usage
        self._ledger = ledger
        self._artifacts = artifacts
        self._locks = locks
        self._diagnostics = diagnostics
        self._localizer = localizer

    def preview(self, job: str, sessions: Sequence[str]) -> list[SessionFootprint]:
        """Report what deleting these sessions would remove, without removing it."""
        self._validate(job, sessions)
        return self._footprints(job, sessions)

    def execute(self, job: str, sessions: Sequence[str]) -> list[SessionFootprint]:
        """Delete the sessions, their recorded usage, and their files.

        Returns:
            One footprint per session asked for, each carrying whether it actually went.
            A session whose files could not be removed keeps its rows and comes back
            marked, rather than taking the rest of the batch down with it.

        Raises:
            SessionRunningError: If one of the sessions has a live client. The batch
                stops there, the same way an unrecorded id stops it -- but unlike that
                check this one cannot be made up front for the whole batch, because the
                claim must still be held when the rows go.
        """
        self._validate(job, sessions)
        # Measured before the first removal, and returned afterwards: once the rows are
        # gone there is nothing left to count, so "what went" has to be taken up front.
        footprints = self._footprints(job, sessions)
        return [self._purge(footprint) for footprint in footprints]

    def _purge(self, footprint: SessionFootprint) -> SessionFootprint:
        """Remove one session's files and then its rows, or report that it stayed.

        The files go first. They are what nothing else can find again: a row names its
        session and can be asked for a second time, while a file whose row is gone is
        invisible to every listing the tool has. So a failure here leaves a session that
        still lists, still resumes, and still deletes on the next attempt -- which is why
        the rows are only reached once the files are actually gone.
        """
        job, session = footprint.job, footprint.session
        # Held across both removals: a client cannot start against this session in the
        # gap between its files going and its rows going.
        with self._locks.claim_session(job, session):
            try:
                self._artifacts.purge_session(job, session)
            except OSError as error:
                self._diagnostics.warning(
                    self._localizer.t("log.session_not_deleted", session=session, error=error),
                    key="log.session_not_deleted",
                )
                return replace(footprint, removed=False)
            self._ledger.purge_session(job, session)
        return footprint

    def _validate(self, job: str, sessions: Sequence[str]) -> None:
        """Reject the whole batch unless every id in it is recorded.

        Raises:
            NoSuchJobError: If the job has no recorded activity.
            NoSuchSessionError: If any session is not recorded for the job.
        """
        if job not in self._store.jobs():
            raise NoSuchJobError("error.job.not_found", job=job)
        recorded = set(self._store.ids_for_job(job))
        for session in sessions:
            if session not in recorded:
                raise NoSuchSessionError("error.session.not_found", session=session, job=job)

    def _footprints(self, job: str, sessions: Sequence[str]) -> list[SessionFootprint]:
        """Measure each session, reading the job's turns and costs once for the batch."""
        turns_per_session: dict[str, int] = {}
        for turn in self._turns.turns_for_job(job):
            turns_per_session[turn.session_id] = turns_per_session.get(turn.session_id, 0) + 1
        costs = self._usage.session_costs(job)
        footprints: list[SessionFootprint] = []
        for session in sessions:
            counts = self._artifacts.counts_for_session(job, session)
            footprints.append(
                SessionFootprint(
                    job=job,
                    session=session,
                    turns=turns_per_session.get(session, 0),
                    cost_usd=costs.get(session, 0.0),
                    contexts=counts.contexts,
                    transcript_calls=counts.transcript_calls,
                )
            )
        return footprints
