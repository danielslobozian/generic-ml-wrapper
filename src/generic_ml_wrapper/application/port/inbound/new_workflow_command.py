# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request to author a new workflow."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewWorkflowCommand:
    """A request to author a new workflow.

    Attributes:
        label: A suggested human name, or ``None`` to let the authoring session settle
            on one at convergence. Only a seed — the session may choose differently, and
            the final label comes from the draft marker — but it lets a name that is
            already taken fail fast, before any work. The slug is derived from it, so the
            author never types kebab-case.
        description: A fuller line to carry into the workflow, or empty.
        client: The client to run the authoring session on.
        guided: Whether to add the guided-facilitation layer (a richer, costlier
            authoring experience) on top of the core interview.
        resume_draft: The key of a draft to reopen instead of starting a fresh
            interview, or ``None``. Takes precedence over ``resume_latest``.
        resume_latest: Reopen the most recent unfinished draft instead of starting a
            fresh interview. Ignored when ``resume_draft`` names one.
    """

    label: str | None
    client: str
    description: str = ""
    guided: bool = False
    resume_draft: str | None = None
    resume_latest: bool = False
