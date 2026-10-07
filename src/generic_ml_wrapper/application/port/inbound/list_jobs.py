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
        tags: The tags the user put on it, sorted (empty when none).
    """

    job: str
    session_count: int
    tags: tuple[str, ...] = ()


class ListJobs(ABC):
    """List the jobs that have recorded sessions."""

    @abstractmethod
    def execute(self, tag: str | None = None) -> list[JobSummary]:
        """List the jobs with recorded activity.

        Args:
            tag: Only the jobs carrying this tag (compared case-insensitively), or
                ``None`` for every job.

        Returns:
            One summary per job, sorted by job id.
        """
