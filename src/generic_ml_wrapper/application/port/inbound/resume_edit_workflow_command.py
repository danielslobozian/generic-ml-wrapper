# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request to pick up an interrupted edit of a workflow."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResumeEditWorkflowCommand:
    """A request to pick up an interrupted edit of a workflow.

    Attributes:
        workflow_name: The workflow whose last editing session should be reopened. No
            client is named: the session carries its own.
    """

    workflow_name: str
