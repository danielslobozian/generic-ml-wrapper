# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for editing an existing workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.edit_workflow_command import EditWorkflowCommand


class EditWorkflowUseCase(ABC):
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
            NoEditToResumeError: If a resume was asked for and there is nothing to reopen.
        """
