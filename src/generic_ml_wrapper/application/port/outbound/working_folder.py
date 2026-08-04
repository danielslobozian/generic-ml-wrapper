# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for whether a folder a run needs is actually there."""

from __future__ import annotations

from abc import ABC, abstractmethod


class WorkingFolderPort(ABC):
    """Answer whether the folders a launch depends on still exist.

    Two questions with one cause: a client launched into a folder that has been deleted
    dies with an error from deep inside itself, naming nothing the user can act on. Asking
    first is the only way to say what actually happened.
    """

    @abstractmethod
    def current_exists(self) -> bool:
        """Return whether the directory this process is running in still exists.

        Returns:
            ``False`` when it was removed underneath us.
        """

    @abstractmethod
    def exists(self, folder: str) -> bool:
        """Return whether ``folder`` exists and is a directory.

        Args:
            folder: The folder to check.

        Returns:
            Whether it is there.
        """
