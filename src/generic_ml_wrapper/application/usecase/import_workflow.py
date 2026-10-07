# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ImportWorkflow use case: install a shared workflow, displacing any it replaces.

Replacing is reversible on purpose, and the order is what makes it so. The archive is
asked what it is *before* anything moves, so a file that is not a workflow is refused with
the installed one still in place; and if unpacking fails after the old one has been moved
aside, it is put back.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.archive_status import ArchiveStatus
from generic_ml_wrapper.application.domain.model.identifiers import IdentifierError, WorkflowName
from generic_ml_wrapper.application.port.inbound.import_workflow import (
    ArchiveUnreadableError,
    ImportOutcome,
    ImportWorkflow,
    ImportWorkflowResult,
)
from generic_ml_wrapper.application.port.inbound.new_workflow import WorkflowNameError

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from generic_ml_wrapper.application.port.outbound.workflow_archive import WorkflowArchivePort
    from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort

_RESERVED = frozenset({"create-workflow", "_common"})
_STEPS = "workflow.md"
_TIME_DIGITS = 6  # the HHMMSS half of an export stamp: <slug>-YYYYMMDD-HHMMSS


class ImportWorkflowUseCase(ImportWorkflow):
    """Unpack an archive into the workflows root, backing up anything it displaces."""

    def __init__(
        self,
        workflows: WorkflowSourcePort,
        archive: WorkflowArchivePort,
        backups_root: Path,
        clock: Callable[[], datetime],
    ) -> None:
        """Wire the use case to its ports and the backup root.

        Args:
            workflows: Resolves workflow folders and reports which names are taken.
            archive: Unpacks the archive, and decides what a shared workflow consists of.
            backups_root: Where a displaced workflow is moved. Deliberately *outside* the
                workflows folder: a backup that lived beside the workflows would be
                listed as one, and keeping it out makes that impossible by construction
                rather than by a filter someone must remember.
            clock: Returns "now", for the backup's timestamped name.
        """
        self._workflows = workflows
        self._archive = archive
        self._backups_root = backups_root
        self._clock = clock

    def execute(self, archive: str, *, replace: bool = False) -> ImportWorkflowResult:
        """Import a workflow from an archive."""
        source = Path(archive)
        # Asked first, and answered without touching anything: an archive that is not a
        # workflow is refused while the installed one is still where the user left it.
        # Checking afterwards is what used to leave them with neither.
        self._refuse_unusable(source, archive)
        name = self._name_from(source)
        self._workflows.seed()
        target = Path(self._workflows.folder(name))

        if self._workflows.exists(name) and not replace:
            # Reported rather than overwritten, so the caller can ask the user first.
            return ImportWorkflowResult(ImportOutcome.REFUSED, name, str(target))

        backup = self._install(source, name, target)
        outcome = ImportOutcome.REPLACED if backup else ImportOutcome.IMPORTED
        return ImportWorkflowResult(outcome, name, str(target), backup)

    def _refuse_unusable(self, source: Path, archive: str) -> None:
        """Reject an archive that cannot be imported, before anything has been moved.

        Raises:
            ArchiveUnreadableError: If there is nothing readable there, or what is there
                carries no workflow.
        """
        status = self._archive.inspect(source)
        if status is ArchiveStatus.MISSING:
            raise ArchiveUnreadableError("error.archive.not_found", archive=archive)
        if status is ArchiveStatus.INCOMPLETE:
            raise ArchiveUnreadableError("error.archive.no_workflow", archive=archive, steps=_STEPS)

    def _install(self, source: Path, name: str, target: Path) -> str | None:
        """Clear the folder, unpack into it, and undo the clearing if that fails.

        The two moves cannot be one: a folder cannot be renamed onto a folder that is not
        empty, so there is a moment when neither is at the target path. Putting the old one
        back is what makes that moment survivable rather than merely brief.
        """
        backup = self._displace(name, target) if target.exists() else None
        try:
            self._archive.unpack(source, target)
        except Exception:
            # Whatever the failed attempt left is discarded rather than merged into the
            # workflow being put back.
            shutil.rmtree(target, ignore_errors=True)
            if backup is not None:
                shutil.move(backup, str(target))
            raise
        return backup

    def _name_from(self, archive: Path) -> str:
        """Derive the workflow's slug from the archive's filename.

        The archive is named ``<slug>-<timestamp>.zip`` on export, but it is a file a
        user can rename, so the stem is taken as the intended name and validated like
        any other. A trailing export timestamp is dropped when one is present.
        """
        stem = archive.stem
        head, separator, tail = stem.rpartition("-")
        if separator and len(tail) == _TIME_DIGITS and tail.isdigit():  # <slug>-<date>-<time>
            stem = head.rpartition("-")[0] or head
        try:
            WorkflowName(stem)
        except IdentifierError as error:
            raise WorkflowNameError(error.catalogue_key, **error.params) from error
        if stem in _RESERVED:
            raise WorkflowNameError("error.workflow.reserved_name", name=stem)
        return stem

    def _displace(self, name: str, target: Path) -> str:
        """Move an existing workflow aside, returning where it went.

        Moved rather than deleted so replacing is never a one-way door — the user is
        told where the old one went, and can put it back.
        """
        stamp = self._clock().strftime("%Y%m%d-%H%M%S")
        backup = self._backups_root / name / stamp
        # Stamps have one-second resolution, and moving a folder onto an existing one
        # moves it *inside* it, so a second replacement in the same second would nest the
        # older backup in the newer one. A counter keeps them side by side.
        counter = 1
        while backup.exists():
            counter += 1
            backup = self._backups_root / name / f"{stamp}-{counter}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(backup))
        return str(backup)
