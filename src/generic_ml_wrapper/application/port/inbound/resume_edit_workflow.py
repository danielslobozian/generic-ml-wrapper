# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for reopening an interrupted workflow edit."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.resume_edit_workflow_command import (
    ResumeEditWorkflowCommand,
)


class ResumeEditWorkflowUseCase(ABC):
    """Reopen the most recent editing session of a workflow, in its own folder."""

    @abstractmethod
    def execute(self, command: ResumeEditWorkflowCommand) -> int:
        """Reopen the edit.

        Args:
            command: Names the workflow to pick up.

        Returns:
            The client's exit code.

        Raises:
            WorkflowNameError: When the name is invalid or reserved.
            WorkflowNotFoundError: When no workflow of that name exists.
            NoEditToResumeError: When it has no editing session, or that session's client
                cannot reopen one.
        """
