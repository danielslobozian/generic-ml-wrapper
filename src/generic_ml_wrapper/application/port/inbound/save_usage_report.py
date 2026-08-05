# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for saving a job's usage report to a file."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SaveUsageReportUseCase(ABC):
    """Save a job's recorded usage as a file, returning where it was written."""

    @abstractmethod
    def execute(self, job: str) -> str:
        """Build the job's report, serialise it, and write it to a file.

        Args:
            job: The job identifier.

        Returns:
            Where the file was written, as text for the caller to show.
        """
