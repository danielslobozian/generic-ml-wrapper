# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the connection health report: incidents per local day, newest first."""

from __future__ import annotations

from datetime import UTC, datetime

from _conformance import InMemoryIncidentLog, an_incident

from generic_ml_wrapper.application.domain.model.incident import IncidentKind
from generic_ml_wrapper.application.port.inbound.report_health import DayHealth
from generic_ml_wrapper.application.usecase.report_health import ReportHealthUseCase

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)


def _at(day: int, hour: int = 12) -> float:
    return datetime(2026, 10, day, hour, tzinfo=UTC).timestamp()


def _report(log: InMemoryIncidentLog, days: int = 3, job: str | None = None):
    return ReportHealthUseCase(log, clock=lambda: _NOW).execute(days=days, job=job)


def test_every_day_of_the_window_is_listed_newest_first_quiet_ones_included() -> None:
    log = InMemoryIncidentLog(
        [
            an_incident(at=_at(5)),
            an_incident(at=_at(5), kind=IncidentKind.STREAM_INTERRUPTED),
            an_incident(at=_at(7)),
            an_incident(at=_at(1)),  # outside a three-day window
        ]
    )
    report = _report(log)
    assert report.by_day == (
        DayHealth("2026-10-07", connection_lost=1),
        DayHealth("2026-10-06"),
        DayHealth("2026-10-05", connection_lost=1, stream_interrupted=1),
    )
    assert [i.occurred_at for i in report.incidents] == [_at(7), _at(5), _at(5)]


def test_the_window_starts_at_midnight_of_its_first_day() -> None:
    log = InMemoryIncidentLog([an_incident(at=_at(5, hour=0)), an_incident(at=_at(4, hour=23))])
    assert len(_report(log).incidents) == 1


def test_it_can_be_narrowed_to_one_job() -> None:
    log = InMemoryIncidentLog([an_incident(job="A", at=_at(7)), an_incident(job="B", at=_at(7))])
    report = _report(log, job="A")
    assert [i.job for i in report.incidents] == ["A"]
    assert report.job == "A"


def test_a_window_is_at_least_one_day() -> None:
    assert len(_report(InMemoryIncidentLog(), days=0).by_day) == 1
