# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for authoring a new workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.new_workflow_command import NewWorkflowCommand
from generic_ml_wrapper.application.port.inbound.new_workflow_result import NewWorkflowResult


class NewWorkflowUseCase(ABC):
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
