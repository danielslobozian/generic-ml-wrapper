# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for reporting a job's recorded usage."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.usage_report import UsageReport


class ExportUsageUseCase(ABC):
    """Report the usage recorded for a job."""

    @abstractmethod
    def execute(self, job: str) -> UsageReport:
        """Build a job's usage report.

        Args:
            job: The job identifier.

        Returns:
            The job's per-turn rows, per-model totals, per-session cost, and totals.
        """
