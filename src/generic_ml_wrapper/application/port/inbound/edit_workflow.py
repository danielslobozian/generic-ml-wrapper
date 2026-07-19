# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for editing an existing workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EditWorkflowCommand:
    """A request to edit an existing workflow.

    Attributes:
        name: The workflow to edit (lowercase letters, digits, dashes).
        client: The client to run the authoring session on.
        guided: Whether to add the guided-facilitation layer (a richer, costlier
            authoring experience) on top of the core interview.
    """

    name: str
    client: str
    guided: bool = False


class WorkflowNotFoundError(ValueError):
    """Raised when the workflow to edit does not exist."""


class EditWorkflow(ABC):
    """Open an existing workflow for editing in an authoring session."""

    @abstractmethod
    def execute(self, command: EditWorkflowCommand) -> int:
        """Run the authoring session against an existing workflow.

        Args:
            command: The request describing the workflow name and client.

        Returns:
            The client's exit code.

        Raises:
            WorkflowNameError: If the name is invalid or reserved.
            WorkflowNotFoundError: If no workflow with that name exists.
        """
