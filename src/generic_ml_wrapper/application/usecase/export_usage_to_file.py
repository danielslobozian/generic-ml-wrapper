# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ExportUsageToFileUseCase use case: build a job's report, serialise it, write it to a file."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.export_usage_query import (
    ExportUsageQuery,
)
from generic_ml_wrapper.application.port.inbound.export_usage_to_file import (
    ExportUsageToFileUseCase,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.inbound.export_usage import ExportUsageUseCase
    from generic_ml_wrapper.application.port.outbound.report_export import ReportExportPort


class ExportUsageToFileService(ExportUsageToFileUseCase):
    """Compose the usage report and hand its JSON to the export writer."""

    def __init__(self, export: ExportUsageUseCase, exporter: ReportExportPort) -> None:
        """Wire the use case to the report source and the file writer.

        Args:
            export: Builds the job's usage report (the same one ``gmlw export`` reads).
            exporter: Writes the serialised report to a file.
        """
        self._export = export
        self._exporter = exporter

    def execute(self, query: ExportUsageQuery) -> str:
        """Build the report, serialise it as JSON, and write it — returning where it went."""
        report = self._export.execute(query)
        content = json.dumps(asdict(report), indent=2)
        return self._exporter.write(query.job, content)
