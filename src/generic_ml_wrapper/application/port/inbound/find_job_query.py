# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request to find one job and everything recorded against it."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FindJobQuery:
    """A request to find one job and everything recorded against it.

    Attributes:
        job: The job identifier, as the user typed or picked it — unvalidated here, so
            an ill-formed name is refused by the same path as an unknown one.
    """

    job: str
