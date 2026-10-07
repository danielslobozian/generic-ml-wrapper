# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListJobs use case: summarise each job's recorded sessions."""

from __future__ import annotations

from generic_ml_wrapper.application.port.inbound.list_jobs import JobSummary, ListJobs
from generic_ml_wrapper.application.port.outbound.job_tag_store import JobTagStorePort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort


class ListJobsUseCase(ListJobs):
    """Summarise each job that has recorded sessions."""

    def __init__(self, store: SessionStorePort, tags: JobTagStorePort) -> None:
        """Wire the use case to the session store and the tags.

        Args:
            store: Where jobs and their sessions are read from.
            tags: Where each job's tags are read from.
        """
        self._store = store
        self._tags = tags

    def execute(self, tag: str | None = None) -> list[JobSummary]:
        """List the jobs with recorded activity, optionally only those with ``tag``.

        Returns:
            One summary per job, sorted by job id.
        """
        wanted = None if tag is None else tag.strip().lower()
        tags = self._tags.tags_by_job()
        return [
            JobSummary(
                job=job,
                session_count=len(self._store.ids_for_job(job)),
                tags=tags.get(job, ()),
            )
            for job in self._store.jobs()
            if wanted is None or wanted in tags.get(job, ())
        ]
