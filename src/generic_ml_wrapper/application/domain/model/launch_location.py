# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Whether the folder a launch needs is there, and which folder was missing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LaunchLocationProblem(Enum):
    """What is wrong with where a run was asked to happen.

    Attributes:
        NONE: Nothing; the launch can proceed.
        CURRENT_GONE: The directory this process is running in has been removed.
        SESSION_FOLDER_GONE: The folder a resumed session ran in has been removed.
    """

    NONE = "none"
    CURRENT_GONE = "current_gone"
    SESSION_FOLDER_GONE = "session_folder_gone"


@dataclass(frozen=True)
class LaunchLocation:
    """The verdict on where a run was asked to happen.

    Attributes:
        problem: What is wrong, or :attr:`LaunchLocationProblem.NONE`.
        folder: The folder that is missing, when one is named; ``None`` otherwise.
    """

    problem: LaunchLocationProblem
    folder: str | None = None

    @property
    def usable(self) -> bool:
        """Whether the launch can go ahead."""
        return self.problem is LaunchLocationProblem.NONE
