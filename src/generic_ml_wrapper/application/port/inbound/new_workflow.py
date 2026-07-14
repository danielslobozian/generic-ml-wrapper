# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for authoring a new workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class NewWorkflowCommand:
    """A request to author a new workflow.

    Attributes:
        name: The new workflow's name (lowercase letters, digits, dashes).
        client: The client to run the authoring session on.
    """

    name: str
    client: str


class WorkflowNameError(ValueError):
    """Raised when a workflow name is invalid or reserved."""


class WorkflowExistsError(ValueError):
    """Raised when a workflow with the requested name already exists."""


class NewWorkflow(ABC):
    """Author a new workflow through the create-workflow interview."""

    @abstractmethod
    def execute(self, command: NewWorkflowCommand) -> int:
        """Run the authoring session for a new workflow.

        Args:
            command: The request describing the workflow name and client.

        Returns:
            The client's exit code.

        Raises:
            WorkflowNameError: If the name is invalid or reserved.
            WorkflowExistsError: If a workflow with that name already exists.
        """
