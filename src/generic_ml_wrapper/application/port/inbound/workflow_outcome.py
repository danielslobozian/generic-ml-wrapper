# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""How an authoring session resolved."""

from __future__ import annotations

from enum import Enum


class WorkflowOutcome(Enum):
    """How an authoring session resolved.

    Attributes:
        DEPLOYED: The draft was named, finished, and moved into ``workflows/<name>/``.
        COLLISION: The chosen name is already taken; the draft is kept for the user.
        INCOMPLETE: The session left no finished marker; the draft is kept to resume.
    """

    DEPLOYED = "deployed"
    COLLISION = "collision"
    INCOMPLETE = "incomplete"
