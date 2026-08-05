# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListJobsUseCase use case: summarise each job's recorded sessions.

The authoring job is left out. It is an ordinary job everywhere else -- deletable,
metered, resumable through the authoring commands -- but its name is chosen by the
system rather than typed by the user, so listing it would show work nobody asked to
start. It is the only name this use case knows about, and the only one it hides.
"""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.authoring_job import AuthoringJob
from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary, ListJobsUseCase
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort


class ListJobsService(ListJobsUseCase):
    """Summarise each job that has recorded sessions."""

    def __init__(self, store: SessionStorePort) -> None:
        """Wire the use case to the session store.

        Args:
            store: Where jobs and their sessions are read from.
        """
        self._store = store

    def execute(self) -> list[JobSummary]:
        """List the jobs with recorded activity, except the authoring job.

        Returns:
            One summary per job, sorted by job id.
        """
        return [
            JobSummary(job=job, session_count=len(self._store.ids_for_job(job)))
            for job in self._store.jobs()
            if job != AuthoringJob.NAME
        ]
