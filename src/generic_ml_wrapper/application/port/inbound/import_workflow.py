# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for importing a workflow from a shareable archive."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.import_workflow_result import ImportWorkflowResult


class ImportWorkflowUseCase(ABC):
    """Install a workflow from an archive, displacing any it replaces."""

    @abstractmethod
    def execute(self, archive: str, *, replace: bool = False) -> ImportWorkflowResult:
        """Import a workflow from an archive.

        Args:
            archive: The archive to read.
            replace: Whether to displace an existing workflow of the same name. Without
                it an existing name is reported back rather than overwritten, so the
                caller can ask the user first.

        Returns:
            How the import resolved, and where things landed.

        Raises:
            ArchiveUnreadableError: If the archive cannot be read or carries no workflow.
            WorkflowNameError: If the archive's workflow name is invalid or reserved.
        """
