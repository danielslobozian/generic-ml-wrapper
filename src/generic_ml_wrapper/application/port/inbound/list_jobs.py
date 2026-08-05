# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing the jobs with recorded activity."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.job_summary import JobSummary


class ListJobsUseCase(ABC):
    """List the jobs that have recorded sessions."""

    @abstractmethod
    def execute(self) -> list[JobSummary]:
        """List the jobs with recorded activity.

        Returns:
            One summary per job, sorted by job id.
        """
