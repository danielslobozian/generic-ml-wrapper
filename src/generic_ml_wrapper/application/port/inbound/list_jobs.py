# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing the jobs with recorded activity."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class JobSummary:
    """A one-line summary of a job's recorded activity.

    Attributes:
        job: The job identifier.
        session_count: How many sessions have been recorded for the job.
    """

    job: str
    session_count: int


class ListJobs(ABC):
    """List the jobs that have recorded sessions."""

    @abstractmethod
    def execute(self) -> list[JobSummary]:
        """List the jobs with recorded activity.

        Returns:
            One summary per job, sorted by job id.
        """
