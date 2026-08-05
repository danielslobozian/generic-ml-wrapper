# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for removing whole jobs and everything recorded under them."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from generic_ml_wrapper.application.port.inbound.job_footprint import JobFootprint


class DeleteJobsUseCase(ABC):
    """Remove whole jobs: their sessions, their usage, and their files."""

    @abstractmethod
    def preview(self, jobs: Sequence[str]) -> list[JobFootprint]:
        """Report what deleting these jobs would remove, without removing it.

        Args:
            jobs: The job ids to measure, in the order given.

        Returns:
            One footprint per job, in the order given.

        Raises:
            NoSuchJobError: If any job has no recorded activity.
        """

    @abstractmethod
    def execute(self, jobs: Sequence[str]) -> list[JobFootprint]:
        """Delete the jobs, their sessions, their recorded usage, and their files.

        The whole batch is validated before anything is removed: one unknown id leaves
        every other job untouched.

        Args:
            jobs: The job ids to delete, in the order given.

        Returns:
            One footprint per deleted job -- what was actually removed.

        Raises:
            NoSuchJobError: If any job has no recorded activity.
        """
