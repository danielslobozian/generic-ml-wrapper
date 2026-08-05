# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``WorkflowBackupPort`` over a folder of displaced workflows.

Backups live under their own root, deliberately outside the workflows folder: a folder
under ``workflows`` with a ``workflow.md`` in it lists as runnable, so keeping backups out
makes "a backup is never a workflow" structural rather than a filter someone has to
remember.

A backup is named for the moment it was made, ``<root>/<name>/<YYYYMMDD-HHMMSS>``, and the
name is made unique before anything is moved. A timestamp alone is not enough: moving a
directory onto an existing directory of the same name does not fail, it moves *inside* it,
so two replacements inside one second would leave the second backup nested in the first
and the older copy that much harder to find.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.workflow_backup import WorkflowBackup
from generic_ml_wrapper.application.port.outbound.workflow_backup import WorkflowBackupPort

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from pathlib import Path

_STAMP = "%Y%m%d-%H%M%S"


class FilesystemWorkflowBackupAdapter(WorkflowBackupPort):
    """Displace workflows into a timestamped folder under the backups root."""

    def __init__(self, root: Path, clock: Callable[[], datetime]) -> None:
        """Bind the backups to their root and the clock that names them.

        Args:
            root: The directory displaced workflows are moved into.
            clock: Returns "now", for the backup's timestamped name; injected so the name
                is deterministic in tests.
        """
        self._root = root
        self._clock = clock

    def displace(self, name: str, folder: Path) -> WorkflowBackup | None:
        """Move the folder's contents into a fresh backup, or report there were none."""
        if not folder.exists():
            return None
        destination = self._free_path(name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(folder), str(destination))
        return WorkflowBackup(name, str(destination))

    def restore(self, backup: WorkflowBackup, folder: Path) -> None:
        """Put the displaced workflow back, discarding whatever replaced it."""
        shutil.rmtree(folder, ignore_errors=True)
        folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(backup.location, str(folder))

    def _free_path(self, name: str) -> Path:
        """The backup folder to use: the timestamp, or the first suffix nobody has taken.

        Second resolution is what a person reads, so it stays the name; uniqueness is
        added only when that name is already there. The alternative -- a random id in
        every name -- would make the common case unreadable to pay for the rare one.
        """
        base = self._root / name / self._clock().strftime(_STAMP)
        if not base.exists():
            return base
        for suffix in range(2, 1000):
            candidate = base.with_name(f"{base.name}-{suffix}")
            if not candidate.exists():
                return candidate
        message = f"no free backup name for {name} at {base}"
        raise FileExistsError(message)
