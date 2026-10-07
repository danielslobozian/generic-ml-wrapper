# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the connection incidents recorded during sessions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.incident import Incident


class IncidentLogPort(ABC):
    """Record connection incidents, and read them back."""

    @abstractmethod
    def record(self, incident: Incident) -> None:
        """Keep one incident."""

    @abstractmethod
    def incidents(self, job: str | None = None, since: float | None = None) -> list[Incident]:
        """Return the recorded incidents, oldest first.

        Args:
            job: Only this job's, or ``None`` for every job.
            since: Only those at or after this time (epoch seconds), or ``None`` for all.
        """
