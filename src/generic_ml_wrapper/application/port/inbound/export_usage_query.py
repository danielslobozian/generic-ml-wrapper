# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request for one job's recorded usage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportUsageQuery:
    """A request for one job's recorded usage.

    Attributes:
        job: The job whose turns and costs are being asked for.
    """

    job: str
