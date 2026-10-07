# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for importing a workflow from a shareable archive."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from generic_ml_wrapper.common.errors import DomainError


class ImportOutcome(Enum):
    """How an import resolved.

    Attributes:
        IMPORTED: The workflow was installed; nothing was displaced.
        REPLACED: A workflow of the same name was displaced into a backup first.
        REFUSED: A workflow of the same name exists and replacing it was declined.
    """

    IMPORTED = "imported"
    REPLACED = "replaced"
    REFUSED = "refused"


@dataclass(frozen=True)
class ImportWorkflowResult:
    """The result of importing a workflow.

    Attributes:
        outcome: How the import resolved.
        name: The workflow's slug.
        path: The installed workflow's folder, or the existing one when refused.
        backup: Where the displaced workflow was moved, or ``None`` when none was.
    """

    outcome: ImportOutcome
    name: str
    path: str
    backup: str | None = None


class ArchiveUnreadableError(DomainError, ValueError):
    """Raised when the archive is missing, not a zip, or holds no workflow."""


class ImportWorkflow(ABC):
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
