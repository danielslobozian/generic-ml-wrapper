# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ReportHealth use case: connection incidents per day, and the latest ones."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.incident import IncidentKind
from generic_ml_wrapper.application.port.inbound.report_health import (
    DayHealth,
    HealthReport,
    ReportHealth,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.application.port.outbound.incident_log import IncidentLogPort


class ReportHealthUseCase(ReportHealth):
    """Read the incident log over a window of local days and count it per day."""

    def __init__(self, incidents: IncidentLogPort, clock: Callable[[], datetime]) -> None:
        """Wire the use case to the incident log and a clock.

        Args:
            incidents: Where the incidents are read from.
            clock: Returns "now" as an aware local time, so days are the user's days.
        """
        self._incidents = incidents
        self._clock = clock

    def execute(self, days: int = 7, job: str | None = None) -> HealthReport:
        """Report the last ``days`` local days, today included."""
        days = max(days, 1)
        now = self._clock()
        today = now.date()
        first = today - timedelta(days=days - 1)
        start = datetime.combine(first, datetime.min.time(), tzinfo=now.tzinfo)
        recorded = self._incidents.incidents(job=job, since=start.timestamp())
        counts: dict[str, dict[IncidentKind, int]] = {}
        for incident in recorded:
            day = datetime.fromtimestamp(incident.occurred_at, tz=now.tzinfo).date().isoformat()
            per_kind = counts.setdefault(day, {})
            per_kind[incident.kind] = per_kind.get(incident.kind, 0) + 1
        by_day = tuple(
            DayHealth(
                day=day,
                connection_lost=counts.get(day, {}).get(IncidentKind.CONNECTION_LOST, 0),
                stream_interrupted=counts.get(day, {}).get(IncidentKind.STREAM_INTERRUPTED, 0),
            )
            for day in ((today - timedelta(days=back)).isoformat() for back in range(days))
        )
        return HealthReport(days=days, job=job, by_day=by_day, incidents=tuple(reversed(recorded)))
