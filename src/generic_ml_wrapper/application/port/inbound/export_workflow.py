# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for exporting a workflow as a shareable archive."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ExportWorkflowUseCase(ABC):
    """Pack an existing workflow into an archive under the exports folder."""

    @abstractmethod
    def execute(self, name: str) -> str:
        """Export a workflow, returning the path to the archive written.

        Args:
            name: The workflow's slug.

        Returns:
            The absolute path to the written archive.

        Raises:
            WorkflowNameError: If the name is invalid or reserved.
            WorkflowNotFoundError: If no workflow with that name exists.
        """
