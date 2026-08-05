# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for writing a usage report to a user-facing file."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ReportExportPort(ABC):
    """Persist a rendered usage report to a file the user can open elsewhere."""

    @abstractmethod
    def write(self, job: str, content: str) -> str:
        """Write ``content`` as this job's export, returning where it was written.

        The destination comes back as text, not as a filesystem type: it is an answer to
        be shown, and nobody above this line opens it, joins onto it, or reads from it.
        The words placed around it are the delivery layer's, which is where the
        localiser lives.

        Args:
            job: The job the report belongs to (used to name the file).
            content: The already-serialised report (e.g. JSON).

        Returns:
            Where the file was written — so the destination is surfaced, never silent.
        """
