# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The axis a rule lives on — the two facets that describe the user."""

from __future__ import annotations

from enum import Enum


class RuleAxis(Enum):
    """The axis a rule lives on — the two facets that describe the user.

    ``ENVIRONMENT`` rules are constraints of the place (company, project, tooling);
    ``ROLE`` rules are the user's own preferences about the craft. On conflict the
    environment wins: a constraint is not overridden by a preference.
    """

    ENVIRONMENT = "environment"
    ROLE = "role"
