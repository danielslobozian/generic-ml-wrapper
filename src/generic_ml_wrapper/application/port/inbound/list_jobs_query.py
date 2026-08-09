# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request for the jobs with recorded activity."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListJobsQuery:
    """A request for the jobs with recorded activity.

    Carries nothing today: the listing takes no criteria yet, and the type exists so that
    adding one later does not change every caller's shape.
    """
