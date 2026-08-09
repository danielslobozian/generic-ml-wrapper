# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for finding a job and its sessions."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.domain.model.job import Job
from generic_ml_wrapper.application.port.inbound.find_job_query import FindJobQuery


class FindJobUseCase(ABC):
    """Find one job and the sessions recorded against it."""

    @abstractmethod
    def execute(self, query: FindJobQuery) -> Job:
        """Find the job.

        Args:
            query: Names the job to find.

        Returns:
            The job with its sessions, oldest first — the caller asks the aggregate which
            session it wants rather than asking here a second time.

        Raises:
            NoSuchJobError: When no job of that name exists. A job that exists but has
                never run is not this error; it comes back with no sessions.
        """
