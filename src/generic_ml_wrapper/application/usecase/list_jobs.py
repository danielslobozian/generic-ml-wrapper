# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListJobs use case: summarise each job's recorded sessions."""

from __future__ import annotations

from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary, ListJobs
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort


class ListJobsUseCase(ListJobs):
    """Summarise each job that has recorded sessions."""

    def __init__(self, store: SessionStorePort) -> None:
        """Wire the use case to the session store.

        Args:
            store: Where jobs and their sessions are read from.
        """
        self._store = store

    def execute(self) -> list[JobSummary]:
        """List the jobs with recorded activity.

        Returns:
            One summary per job, sorted by job id.
        """
        return [
            JobSummary(job=job, session_count=len(self._store.ids_for_job(job)))
            for job in self._store.jobs()
        ]
