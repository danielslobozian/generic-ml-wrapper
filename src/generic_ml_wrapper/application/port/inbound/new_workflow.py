# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for authoring a new workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class NewWorkflowCommand:
    """A request to author a new workflow.

    Attributes:
        name: A suggested name (lowercase letters, digits, dashes), or ``None`` to let
            the authoring session propose one at convergence. When given, it is only a
            seed — the session may rename it, and the final name comes from the draft
            marker — but it lets a known name fail fast on a collision before any work.
        client: The client to run the authoring session on.
    """

    name: str | None
    client: str


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


@dataclass(frozen=True)
class NewWorkflowResult:
    """The result of an authoring session.

    Attributes:
        exit_code: The authoring client's exit code.
        outcome: How the draft resolved (deployed / collision / incomplete).
        name: The workflow name the session settled on, or ``None`` if it named none.
        draft_path: The draft folder — the deployed location on success, or where the
            kept draft still lives on a collision or an incomplete run.
    """

    exit_code: int
    outcome: WorkflowOutcome
    name: str | None
    draft_path: str


class WorkflowNameError(ValueError):
    """Raised when a workflow name is invalid or reserved."""


class WorkflowExistsError(ValueError):
    """Raised when a workflow with the requested name already exists."""


class NewWorkflow(ABC):
    """Author a new workflow through the create-workflow interview."""

    @abstractmethod
    def execute(self, command: NewWorkflowCommand) -> NewWorkflowResult:
        """Run the authoring session for a new workflow.

        Args:
            command: The request describing the (optional) name and the client.

        Returns:
            The result: the client's exit code and how the draft resolved.

        Raises:
            WorkflowNameError: If a given name is invalid or reserved.
            WorkflowExistsError: If a given name already exists (fail fast, up front).
        """
