# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The FindJobUseCase use case: read one job and the sessions filed under it."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.job import Job
from generic_ml_wrapper.application.domain.model.job_id import JobId
from generic_ml_wrapper.application.domain.model.no_such_job_error import NoSuchJobError
from generic_ml_wrapper.application.port.inbound.find_job import FindJobUseCase
from generic_ml_wrapper.application.port.inbound.find_job_query import FindJobQuery
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort


class FindJobService(FindJobUseCase):
    """Read one job and the sessions filed under it."""

    def __init__(self, store: SessionStorePort) -> None:
        """Wire the use case to the session store.

        Args:
            store: Where the job and its sessions are read from.
        """
        self._store = store

    def execute(self, query: FindJobQuery) -> Job:
        """Find the job.

        Args:
            query: Names the job to find.

        Returns:
            The job with its sessions in the order the store recorded them.

        Raises:
            NoSuchJobError: When no job of that name exists.
        """
        if query.job not in self._store.jobs():
            raise NoSuchJobError("error.job.not_found", job=query.job)
        return Job(
            job_id=JobId(query.job),
            sessions=tuple(self._store.sessions_for_job(query.job)),
        )
