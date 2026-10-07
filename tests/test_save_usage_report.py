# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the SaveUsageReport use case and the filesystem report exporter."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.store.filesystem_report_exporter import (
    FilesystemReportExporter,
)
from generic_ml_wrapper.application.port.inbound.export_usage import (
    ModelTotal,
    SessionCost,
    UsageReport,
)
from generic_ml_wrapper.application.usecase.save_usage_report import SaveUsageReportUseCase


class _FakeExport:
    def __init__(self, report: UsageReport) -> None:
        self._report = report
        self.seen: str | None = None

    def execute(self, job: str) -> UsageReport:
        self.seen = job
        return self._report


class _RecordingExporter:
    def __init__(self, path: Path) -> None:
        self._path = path
        self.job: str | None = None
        self.content: str | None = None

    def write(self, job: str, content: str) -> Path:
        self.job, self.content = job, content
        return self._path


def _report() -> UsageReport:
    return UsageReport(
        job="alpha",
        models=(ModelTotal("claude", 2, 100, 50, 10, 1.5),),
        session_costs=(SessionCost("alpha_001", 0.8),),
        turn_count=2,
        total_usd=0.8,
    )


def test_save_usage_report_serialises_json_and_returns_the_written_path() -> None:
    exporter = _RecordingExporter(Path("/exports/alpha-x.json"))
    export = _FakeExport(_report())
    use_case = SaveUsageReportUseCase(export=export, exporter=exporter)  # type: ignore[arg-type]

    result = use_case.execute("alpha")

    assert result == Path("/exports/alpha-x.json")
    assert export.seen == "alpha"
    assert exporter.job == "alpha"
    payload = json.loads(exporter.content or "")
    assert payload["job"] == "alpha"  # the report round-trips as JSON
    assert payload["turn_count"] == 2
    assert payload["models"][0]["model"] == "claude"


def test_filesystem_report_exporter_writes_a_timestamped_file(tmp_path: Path) -> None:
    root = tmp_path / "exports"  # deliberately absent — the exporter must create it
    clock = lambda: datetime(2026, 7, 24, 10, 15, 0, tzinfo=UTC)  # noqa: E731 (fixed test clock)
    exporter = FilesystemReportExporter(root, clock=clock)

    path = exporter.write("alpha", '{"job": "alpha"}')

    assert path == root / "alpha-20260724-101500.json"
    assert path.read_text(encoding="utf-8") == '{"job": "alpha"}'
    assert root.is_dir()  # the root was created
