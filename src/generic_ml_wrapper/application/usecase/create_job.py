# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The CreateJobUseCase use case: bring a job into existence, sessions or not."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.job import Job
from generic_ml_wrapper.application.domain.model.job_id import JobId
from generic_ml_wrapper.application.port.inbound.create_job import CreateJobUseCase
from generic_ml_wrapper.application.port.inbound.create_job_command import CreateJobCommand
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort


class CreateJobService(CreateJobUseCase):
    """Bring a job into existence, sessions or not."""

    def __init__(self, store: SessionStorePort) -> None:
        """Wire the use case to the session store.

        Args:
            store: Where the job is recorded.
        """
        self._store = store

    def execute(self, command: CreateJobCommand) -> Job:
        """Create the job, or return it unchanged when it already exists.

        Args:
            command: Names the job to create.

        Returns:
            The job with whatever sessions it already had — none, for a new one.

        Raises:
            IdentifierError: When the name is not a valid job identifier.
        """
        job_id = JobId(command.job)
        self._store.create_job(str(job_id))
        return Job(job_id=job_id, sessions=tuple(self._store.sessions_for_job(str(job_id))))
