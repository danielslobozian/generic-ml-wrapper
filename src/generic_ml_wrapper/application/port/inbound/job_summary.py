# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A one-line summary of a job's recorded activity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobSummary:
    """A one-line summary of a job's recorded activity.

    Attributes:
        job: The job identifier.
        session_count: How many sessions have been recorded for the job.
    """

    job: str
    session_count: int
