# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``ReportExportPort``: write a usage report to a timestamped JSON file."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.report_export import ReportExportPort

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from pathlib import Path


class FilesystemReportExporter(ReportExportPort):
    """Write each export to ``<root>/<job>-<timestamp>.json``, creating the root as needed."""

    def __init__(self, root: Path, clock: Callable[[], datetime]) -> None:
        """Bind the exporter to its output root and a clock (for the filename timestamp).

        Args:
            root: The directory export files are written under.
            clock: Returns "now"; injected so the timestamped filename is deterministic in tests.
        """
        self._root = root
        self._clock = clock

    def write(self, job: str, content: str) -> Path:
        """Write ``content`` to a timestamped file under the root, returning its path."""
        self._root.mkdir(parents=True, exist_ok=True)
        stamp = self._clock().strftime("%Y%m%d-%H%M%S")
        path = self._root / f"{job}-{stamp}.json"
        path.write_text(content, encoding="utf-8")
        return path
