# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for authoring a new workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


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


class WorkflowNameError(DomainError, ValueError):
    """Raised when a workflow name is invalid or reserved."""


class WorkflowExistsError(ValueError):
    """Raised when a workflow with the requested name already exists."""


class NoSuchDraftError(DomainError, ValueError):
    """Raised when a draft asked for by key does not exist, or none is resumable."""


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
            NoSuchDraftError: If a resume was asked for and no such draft exists.
        """
