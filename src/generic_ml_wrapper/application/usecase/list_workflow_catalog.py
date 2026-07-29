# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListWorkflowCatalog use case: workflows with their labels and descriptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_workflow_catalog import ListWorkflowCatalog

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.workflow import Workflow
    from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort


class ListWorkflowCatalogUseCase(ListWorkflowCatalog):
    """List the described workflows from the workflow source."""

    def __init__(self, workflows: WorkflowSourcePort) -> None:
        """Wire the use case to the workflow source.

        Args:
            workflows: Where the workflows and their sidecars are read from.
        """
        self._workflows = workflows

    def execute(self) -> list[Workflow]:
        """List the workflows, sorted by slug."""
        return self._workflows.catalog()
