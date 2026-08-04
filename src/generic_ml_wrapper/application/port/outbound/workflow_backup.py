# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for moving a workflow out of the way, and putting it back.

Replacing a workflow is two steps that must be undoable between them: the one already
installed is moved aside, and the new one is written in its place. If the second step
fails, the first has to be reversed, or the user is left with neither.

The port is shaped around that job rather than around the filesystem. There is no
``move``, no ``mkdir``, no ``copy`` -- a port of those would have relocated the I/O
without relocating the decision, and the use case would still be writing filesystem logic
one layer further down. What the use case knows is "displace this" and "put it back"; what
a backup is called, where it lives, and how a name is kept from colliding with an earlier
one are the implementation's own business.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_wrapper.application.domain.model.workflow_backup import WorkflowBackup


class WorkflowBackupPort(ABC):
    """Move an installed workflow out of the way, reversibly."""

    @abstractmethod
    def displace(self, name: str, folder: Path) -> WorkflowBackup | None:
        """Move whatever occupies the folder out of it, and report where it went.

        ``None`` when the folder was not occupied, so a caller can ask "displace this"
        without first asking whether there is anything to displace -- which it could only
        answer by looking at the disk itself. Note that *occupied* is not the same
        question as *is a runnable workflow*: a folder left behind by an interrupted
        import holds no ``workflow.md`` and is still displaced, because unpacking over it
        would fold its leftovers into the workflow arriving.

        The folder is left absent afterwards, ready for its replacement. The backup is
        kept somewhere a workflow listing cannot reach, so a displaced workflow is never
        mistaken for an installed one.

        Implementations must not overwrite or nest inside an earlier backup of the same
        workflow: two replacements in quick succession are ordinary, and the older copy is
        the one a user is most likely to want back.

        Args:
            name: The workflow's slug.
            folder: The folder it currently occupies.

        Returns:
            Where the displaced workflow now lives, or ``None`` if the folder was empty.
        """

    @abstractmethod
    def restore(self, backup: WorkflowBackup, folder: Path) -> None:
        """Put a displaced workflow back in its folder.

        Called when whatever was meant to replace it did not arrive. Anything left in the
        folder by the failed attempt is discarded first -- a half-written replacement is
        not something to merge with, and keeping it would leave the restored workflow
        holding files it never had.

        Args:
            backup: The displaced workflow, as :meth:`displace` reported it.
            folder: The folder to put it back into.
        """
