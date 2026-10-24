# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListJobs use case: summarise each job's recorded sessions."""

from __future__ import annotations

from datetime import UTC, datetime

from generic_ml_wrapper.application.domain.model.job_order import JobOrder
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary, ListJobs
from generic_ml_wrapper.application.port.outbound.job_activity import JobActivityPort
from generic_ml_wrapper.application.port.outbound.job_tag_store import JobTagStorePort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort


class ListJobsUseCase(ListJobs):
    """Summarise each job that has recorded sessions."""

    def __init__(
        self, store: SessionStorePort, tags: JobTagStorePort, activity: JobActivityPort
    ) -> None:
        """Wire the use case to the session store, the tags, and when jobs were worked on.

        Args:
            store: Where jobs and their sessions are read from.
            tags: Where each job's tags are read from.
            activity: Where each job's latest turn is read from.
        """
        self._store = store
        self._tags = tags
        self._activity = activity

    def execute(self, tag: str | None = None, order: JobOrder = JobOrder.NAME) -> list[JobSummary]:
        """List the jobs with recorded activity, optionally only those with ``tag``.

        Returns:
            One summary per job, by job id, or the latest worked on first.
        """
        wanted = None if tag is None else tag.strip().lower()
        tags = self._tags.tags_by_job()
        last_turns = self._activity.last_turn_by_job()
        summaries: list[JobSummary] = []
        for job in self._store.jobs():
            if wanted is not None and wanted not in tags.get(job, ()):
                continue
            sessions = self._store.sessions_for_job(job)
            started = [_epoch(s.created_at) for s in sessions]
            known = [moment for moment in (last_turns.get(job), *started) if moment is not None]
            summaries.append(
                JobSummary(
                    job=job,
                    session_count=len(sessions),
                    tags=tags.get(job, ()),
                    last_worked_at=max(known) if known else None,
                )
            )
        if order is JobOrder.RECENT:
            # Newest first; a job never worked on goes last. The sort is stable, so ties
            # keep the store's order by name.
            summaries.sort(key=lambda summary: -(summary.last_worked_at or 0.0))
        return summaries


def _epoch(created_at: str | None) -> float | None:
    """A session's recorded start as epoch seconds; the ledger writes UTC without a zone."""
    if not created_at:
        return None
    try:
        moment = datetime.fromisoformat(created_at)
    except ValueError:
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).timestamp()
