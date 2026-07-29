# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for packing and unpacking a workflow as a shareable archive."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class WorkflowArchivePort(ABC):
    """Pack a workflow folder into an archive, and unpack one back out.

    Both directions carry the same, deliberately narrow set of files: a workflow is
    shared as its steps, the words describing it, and the scripts it runs — nothing
    else. What is left behind is left behind on purpose, and the implementation says
    which and why.
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
