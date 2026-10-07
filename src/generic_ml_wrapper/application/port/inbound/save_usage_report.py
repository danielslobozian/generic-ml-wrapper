# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for saving a job's usage report to a file."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class SaveUsageReport(ABC):
    """Save a job's recorded usage as a file, returning where it was written."""

    @abstractmethod
    def execute(self, job: str) -> Path:
        """Build the job's report, serialise it, and write it to a file.

        Args:
            job: The job identifier.

        Returns:
            The path of the file written.
        """
