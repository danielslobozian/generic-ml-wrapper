# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request to bring a job into existence before anything runs on it."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CreateJobCommand:
    """A request to bring a job into existence before anything runs on it.

    Attributes:
        job: The job identifier to create.
    """

    job: str
