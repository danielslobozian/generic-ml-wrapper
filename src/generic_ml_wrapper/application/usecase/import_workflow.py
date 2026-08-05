# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ImportWorkflowUseCase use case: install a shared workflow, displacing any it replaces.

Replacing is reversible on purpose, and the order is what makes it so. The archive is
asked what it is *before* anything moves, so a file that is not a workflow is refused with
the installed one still in place; and if unpacking fails after the old one has been moved
aside, it is put back. Neither step touches the filesystem here -- what a backup is called
and where it lives belongs to the adapter that owns the disk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.archive_status import ArchiveStatus
from generic_ml_wrapper.application.domain.model.archive_unreadable_error import (
    ArchiveUnreadableError,
)
from generic_ml_wrapper.application.domain.model.workflow_name import WorkflowName
from generic_ml_wrapper.application.domain.model.workflow_name_error import WorkflowNameError
from generic_ml_wrapper.application.port.inbound.import_outcome import ImportOutcome
from generic_ml_wrapper.application.port.inbound.import_workflow import ImportWorkflowUseCase
from generic_ml_wrapper.application.port.inbound.import_workflow_result import ImportWorkflowResult

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.workflow_backup import WorkflowBackup
    from generic_ml_wrapper.application.port.outbound.workflow_archive import WorkflowArchivePort
    from generic_ml_wrapper.application.port.outbound.workflow_backup import WorkflowBackupPort
    from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort

_RESERVED = frozenset({"create-workflow", "_common"})
_STEPS = "workflow.md"


class ImportWorkflowService(ImportWorkflowUseCase):
    """Unpack an archive into the workflows root, backing up anything it displaces."""

    def __init__(
        self,
        workflows: WorkflowSourcePort,
        archive: WorkflowArchivePort,
        backups: WorkflowBackupPort,
    ) -> None:
        """Wire the use case to its ports.

        Args:
            workflows: Resolves workflow folders and reports which names are taken.
            archive: Reports what an archive is, and unpacks it.
            backups: Moves a displaced workflow aside, and puts it back if the
                replacement never arrives.
        """
        self._workflows = workflows
        self._archive = archive
        self._backups = backups

    def execute(self, archive: str, *, replace: bool = False) -> ImportWorkflowResult:
        """Import a workflow from an archive."""
        # Asked first, and answered without touching anything: an archive that is not a
        # workflow is refused while the installed one is still where the user left it.
        # Checking afterwards is what used to leave them with neither.
        self._refuse_unusable(archive)
        name = self._named(archive)
        self._workflows.seed()
        target = self._workflows.folder(name)

        if self._workflows.find(name) is not None and not replace:
            # Reported rather than overwritten, so the caller can ask the user first.
            return ImportWorkflowResult(ImportOutcome.REFUSED, name, target)

        backup = self._install(archive, name, target)
        if backup is None:
            return ImportWorkflowResult(ImportOutcome.IMPORTED, name, target)
        return ImportWorkflowResult(ImportOutcome.REPLACED, name, target, backup.location)

    def _refuse_unusable(self, archive: str) -> None:
        """Reject an archive that cannot be imported, before anything has been moved.

        Raises:
            ArchiveUnreadableError: If there is nothing readable there, or what is there
                carries no workflow.
        """
        status = self._archive.inspect(archive)
        if status is ArchiveStatus.MISSING:
            raise ArchiveUnreadableError("error.archive.not_found", archive=archive)
        if status is ArchiveStatus.INCOMPLETE:
            raise ArchiveUnreadableError("error.archive.no_workflow", archive=archive, steps=_STEPS)

    def _install(self, source: str, name: str, target: str) -> WorkflowBackup | None:
        """Clear the folder, unpack into it, and undo the clearing if that fails.

        Displacing is asked for unconditionally: whether anything was there is a question
        about the disk, and answering it here would mean reaching for the disk. The reply
        says which of the two outcomes happened.

        The two moves cannot be one: a folder cannot be renamed onto a folder that is not
        empty, so there is a moment when neither is at the target path. Putting the old one
        back is what makes that moment survivable rather than merely brief.
        """
        backup = self._backups.displace(name, target)
        try:
            self._archive.unpack(source, target)
        except Exception:
            if backup is not None:
                self._backups.restore(backup, target)
            raise
        return backup

    def _named(self, archive: str) -> str:
        """The workflow the archive says it carries, refused if the name is reserved.

        What a filename yields is :class:`WorkflowName`'s own rule. What may not be
        installed over is this use case's, because *reserved* means reserved by what the
        application seeds -- a fact about the application, not about names.
        """
        name = WorkflowName.from_archive_filename(archive)
        if name in _RESERVED:
            raise WorkflowNameError("error.workflow.reserved_name", name=name)
        return name
