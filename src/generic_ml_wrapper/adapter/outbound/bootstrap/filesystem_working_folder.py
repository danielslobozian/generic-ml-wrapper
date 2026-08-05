# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``WorkingFolderPort`` over the real filesystem."""

from __future__ import annotations

import os
from pathlib import Path

from generic_ml_wrapper.application.port.outbound.working_folder import WorkingFolderPort


class FilesystemWorkingFolderAdapter(WorkingFolderPort):
    """Ask the filesystem whether the folders a launch needs are still there."""

    def current_exists(self) -> bool:
        """Return whether this process's directory still exists.

        A probe rather than a lookup: the only way to learn that a working directory has
        been deleted is to ask for it and be refused.
        """
        try:
            os.getcwd()  # noqa: PTH109  (Path.cwd() would raise the same way; this is the probe)
        except OSError:
            return False
        return True

    def exists(self, folder: str) -> bool:
        """Return whether ``folder`` is a directory that exists."""
        return Path(folder).is_dir()
