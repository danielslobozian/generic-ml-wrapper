# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""How a workflow is authored: the guided interview, or the quick one."""

from __future__ import annotations

from enum import Enum


class AuthoringMode(Enum):
    """Which authoring experience a session runs.

    GUIDED walks the user through the interview; QUICK is the lean path for
    someone who already knows what they want. The choice is offered once, at the start.
    """

    GUIDED = "guided"
    QUICK = "quick"
