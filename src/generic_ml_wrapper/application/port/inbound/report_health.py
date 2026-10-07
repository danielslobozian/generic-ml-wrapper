# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the connection health of recent sessions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.incident import Incident


@dataclass(frozen=True)
class DayHealth:
    """One day's connection incidents, counted by kind.

    Attributes:
        day: The local date, ``YYYY-MM-DD``.
        connection_lost: Requests that failed and were retried by the client.
        stream_interrupted: Answers cut off part way.
    """

    day: str
    connection_lost: int = 0
    stream_interrupted: int = 0


@dataclass(frozen=True)
class HealthReport:
    """The connection incidents over a window of days.

    Attributes:
        days: How many days the window covers, today included.
        job: The job it is narrowed to, or ``None`` for every job.
        by_day: One entry per day of the window, newest first -- quiet days included,
            so a bad day stands out against the ones around it.
        incidents: Every incident in the window, newest first.
    """

    days: int
    job: str | None
    by_day: tuple[DayHealth, ...]
    incidents: tuple[Incident, ...]


class ReportHealth(ABC):
    """Summarise the connection incidents of recent sessions."""

    @abstractmethod
    def execute(self, days: int = 7, job: str | None = None) -> HealthReport:
        """Report the last ``days`` days, optionally for one job only.

        Args:
            days: How many days back, today included (at least one).
            job: Only this job's incidents, or ``None`` for every job.
        """
