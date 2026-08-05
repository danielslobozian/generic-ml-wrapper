# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The CheckLaunchLocation use case: refuse a launch into a folder that is gone."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.launch_location import (
    LaunchLocation,
    LaunchLocationProblem,
)
from generic_ml_wrapper.application.port.inbound.check_launch_location import CheckLaunchLocation

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.working_folder import WorkingFolderPort


class CheckLaunchLocationUseCase(CheckLaunchLocation):
    """Decide whether a run can start where it was asked to."""

    def __init__(self, folders: WorkingFolderPort) -> None:
        """Wire the use case to what can answer whether a folder is there.

        Args:
            folders: Reports whether the current directory and a named folder exist.
        """
        self._folders = folders

    def execute(self, session_folder: str | None = None) -> LaunchLocation:
        """Return the verdict on where the run is about to happen.

        The current directory is checked first because everything depends on it: a client
        launched from a deleted directory dies before it can even be told where to go.
        """
        if not self._folders.current_exists():
            return LaunchLocation(LaunchLocationProblem.CURRENT_GONE)
        if session_folder is not None and not self._folders.exists(session_folder):
            return LaunchLocation(LaunchLocationProblem.SESSION_FOLDER_GONE, session_folder)
        return LaunchLocation(LaunchLocationProblem.NONE)
