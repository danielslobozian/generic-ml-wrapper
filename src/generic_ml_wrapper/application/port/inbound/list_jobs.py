# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing the jobs with recorded activity."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from generic_ml_wrapper.application.domain.model.job_order import JobOrder


@dataclass(frozen=True)
class JobSummary:
    """A one-line summary of a job's recorded activity.

    Attributes:
        job: The job identifier.
        session_count: How many sessions have been recorded for the job.
        tags: The tags the user put on it, sorted (empty when none).
        last_worked_at: When it was last worked on, epoch seconds: its latest turn, else
            its latest session's start; ``None`` when neither is known.
    """

    job: str
    session_count: int
    tags: tuple[str, ...] = ()
    last_worked_at: float | None = None


class ListJobs(ABC):
    """List the jobs that have recorded sessions."""

    @abstractmethod
    def execute(self, tag: str | None = None, order: JobOrder = JobOrder.NAME) -> list[JobSummary]:
        """List the jobs with recorded activity.

        Args:
            tag: Only the jobs carrying this tag (compared case-insensitively), or
                ``None`` for every job.
            order: By job id, or the latest worked on first (a job never worked on last).

        Returns:
            One summary per job, in ``order``.
        """
