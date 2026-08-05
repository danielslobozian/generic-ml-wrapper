# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request to edit an existing workflow."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EditWorkflowCommand:
    """A request to edit an existing workflow.

    Attributes:
        name: The workflow to edit (lowercase letters, digits, dashes).
        client: The client to run the authoring session on.
        guided: Whether to add the guided-facilitation layer (a richer, costlier
            authoring experience) on top of the core interview.
        resume_latest: Reopen this workflow's most recent editing session instead of
            starting a fresh one — an edit interrupted halfway is picked up where it
            stopped rather than begun again.
    """

    name: str
    client: str
    guided: bool = False
    resume_latest: bool = False
