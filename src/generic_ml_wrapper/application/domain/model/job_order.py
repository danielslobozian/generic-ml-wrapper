# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The order a list of jobs is shown in."""

from __future__ import annotations

from enum import StrEnum


class JobOrder(StrEnum):
    """By name, or the latest worked on first.

    The values are the words of the ``[jobs] sort`` setting and of ``gmlw jobs --sort``.
    """

    NAME = "name"
    RECENT = "recent"
