# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for deciding whether a run can happen where it was asked to.

The decision and the filesystem question used to be one function in the command line,
which also printed the guidance. Three things in one place meant none of them could be
tested without the other two.
"""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.launch_location import LaunchLocationProblem
from generic_ml_wrapper.application.port.outbound.working_folder import WorkingFolderPort
from generic_ml_wrapper.application.usecase.check_launch_location import (
    CheckLaunchLocationUseCase,
)


class _Folders(WorkingFolderPort):
    """A filesystem whose answers a test declares."""

    def __init__(self, *, current: bool = True, present: set[str] | None = None) -> None:
        self._current = current
        self._present = present or set()

    def current_exists(self) -> bool:
        return self._current

    def exists(self, folder: str) -> bool:
        return folder in self._present


def test_a_run_in_a_live_directory_may_proceed() -> None:
    assert CheckLaunchLocationUseCase(_Folders()).execute().usable


def test_a_deleted_working_directory_stops_the_run() -> None:
    """A client launched from a deleted directory dies naming nothing the user can act on."""
    verdict = CheckLaunchLocationUseCase(_Folders(current=False)).execute()

    assert not verdict.usable
    assert verdict.problem is LaunchLocationProblem.CURRENT_GONE


def test_a_session_folder_that_is_gone_stops_a_resume_and_is_named() -> None:
    folders = _Folders(present=set())

    verdict = CheckLaunchLocationUseCase(folders).execute("/gone/project")

    assert verdict.problem is LaunchLocationProblem.SESSION_FOLDER_GONE
    assert verdict.folder == "/gone/project"  # named, so the guidance can say which


def test_a_session_folder_that_is_there_may_proceed() -> None:
    folders = _Folders(present={"/work/project"})

    assert CheckLaunchLocationUseCase(folders).execute("/work/project").usable


def test_the_current_directory_is_checked_even_when_resuming() -> None:
    """A session recorded before folders existed resumes in the current directory."""
    folders = _Folders(current=False, present={"/work/project"})

    verdict = CheckLaunchLocationUseCase(folders).execute("/work/project")

    assert verdict.problem is LaunchLocationProblem.CURRENT_GONE
