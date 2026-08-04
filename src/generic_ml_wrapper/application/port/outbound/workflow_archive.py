# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for packing and unpacking a workflow as a shareable archive."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.archive_status import ArchiveStatus

if TYPE_CHECKING:
    from pathlib import Path


class WorkflowArchivePort(ABC):
    """Pack a workflow folder into an archive, and unpack one back out.

    Both directions carry the same, deliberately narrow set of files: a workflow is
    shared as its steps, the words describing it, and the scripts it runs — nothing
    else. What is left behind is left behind on purpose, and the implementation says
    which and why.

    It also answers what an archive *is* before anything is done on its behalf. That
    question belongs here because the answer depends on what a shared workflow consists
    of, which is this port's own definition — and because asking it costs nothing while
    finding out afterwards costs the workflow being replaced.
    """

    @abstractmethod
    def inspect(self, archive: Path) -> ArchiveStatus:
        """Report whether the archive can be imported, without unpacking it.

        Read-only, and it writes nothing anywhere: a caller may ask before it has
        displaced or created anything, which is the point of it existing.

        Args:
            archive: The archive to examine.

        Returns:
            :attr:`ArchiveStatus.MISSING` if there is nothing readable there,
            :attr:`ArchiveStatus.INCOMPLETE` if it carries no workflow, and
            :attr:`ArchiveStatus.COMPLETE` otherwise.
        """

    @abstractmethod
    def pack(self, folder: Path, slug: str) -> Path:
        """Write a workflow folder's portable contents to an archive.

        Args:
            folder: The workflow folder to pack.
            slug: The workflow's id, used to name the archive.

        Returns:
            The path to the written archive.
        """

    @abstractmethod
    def unpack(self, archive: Path, destination: Path) -> None:
        """Extract an archive's portable contents into a destination folder.

        Only the portable files are taken; anything else the archive happens to carry
        is ignored rather than written, so an archive cannot deposit files a workflow
        has no business containing.

        Args:
            archive: The archive to read.
            destination: The folder to populate (created if absent).
        """
