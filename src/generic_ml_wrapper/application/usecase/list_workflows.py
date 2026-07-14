# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListWorkflows use case: the runnable workflow names."""

from __future__ import annotations

from generic_ml_wrapper.application.port.inbound.list_workflows import ListWorkflows
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort


class ListWorkflowsUseCase(ListWorkflows):
    """List the runnable workflows from the workflow source."""

    def __init__(self, workflows: WorkflowSourcePort) -> None:
        """Wire the use case to the workflow source.

        Args:
            workflows: Where the workflows are read from.
        """
        self._workflows = workflows

    def execute(self) -> list[str]:
        """List the runnable workflow names.

        Returns:
            The workflow names, sorted (empty if none exist).
        """
        return self._workflows.names()
