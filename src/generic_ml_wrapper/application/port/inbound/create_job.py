# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for creating a job."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.domain.model.job import Job
from generic_ml_wrapper.application.port.inbound.create_job_command import CreateJobCommand


class CreateJobUseCase(ABC):
    """Bring a job into existence before any session runs on it."""

    @abstractmethod
    def execute(self, command: CreateJobCommand) -> Job:
        """Create the job.

        Args:
            command: Names the job to create.

        Returns:
            The job, with no sessions. Creating one that already exists returns it as it
            stands rather than refusing, so a caller that creates before starting need
            not ask first.

        Raises:
            IdentifierError: When the name is not a valid job identifier.
        """
