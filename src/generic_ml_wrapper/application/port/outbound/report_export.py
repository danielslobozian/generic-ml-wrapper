# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for writing a usage report to a user-facing file."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class ReportExportPort(ABC):
    """Persist a rendered usage report to a file the user can open elsewhere."""

    @abstractmethod
    def write(self, job: str, content: str) -> Path:
        """Write ``content`` as this job's export, returning the file written.

        Args:
            job: The job the report belongs to (used to name the file).
            content: The already-serialised report (e.g. JSON).

        Returns:
            The path of the file written — so the destination is surfaced, never silent.
        """
