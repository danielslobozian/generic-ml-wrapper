# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request to carry on an unfinished create-workflow interview."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResumeCreateWorkflowCommand:
    """A request to carry on an unfinished create-workflow interview.

    Attributes:
        draft_key: The draft to reopen, or ``None`` for the most recent unfinished one.
            No client is named: the draft's session carries its own.
    """

    draft_key: str | None = None
