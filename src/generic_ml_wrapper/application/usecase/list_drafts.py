# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListDraftsUseCase use case: the authoring drafts still awaiting a workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_drafts import ListDraftsUseCase

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.draft import Draft
    from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort


class ListDraftsService(ListDraftsUseCase):
    """List the drafts from the workflow source."""

    def __init__(self, workflows: WorkflowSourcePort) -> None:
        """Wire the use case to the workflow source.

        Args:
            workflows: Where the drafts are read from.
        """
        self._workflows = workflows

    def execute(self) -> list[Draft]:
        """List the drafts, newest first."""
        return self._workflows.drafts()
