# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the two-level session lock.

Ported from the cache's ``test_filesystem_store_lock`` and
``test_filesystem_execution_key_lock``, with one behaviour deliberately inverted: the
cache's per-key lock waits and then proceeds anyway, so a hung peer never blocks a user's
call. Here proceeding anyway would delete a session that is running, so every claim fails
fast instead -- and that difference is what these tests pin.

``flock`` locks belong to an open file description rather than to a process, so two
separate ``open`` calls contend even inside one interpreter. That is what lets a single
test hold a lock and try to claim it without spawning anything.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from generic_ml_wrapper.adapter.outbound.store.filesystem_session_lock import (
    FilesystemSessionLock,
)
from generic_ml_wrapper.application.domain.model.job_running_error import JobRunningError
from generic_ml_wrapper.application.domain.model.session_running_error import SessionRunningError

if TYPE_CHECKING:
    from pathlib import Path

_WINDOWS_HAS_NO_SHARED_MODE = pytest.mark.skipif(
    sys.platform == "win32",
    reason="msvcrt has no shared lock; the job-level hold is a documented no-op there",
)


def test_a_claim_on_a_free_session_is_granted(tmp_path: Path) -> None:
    with FilesystemSessionLock(tmp_path).claim_session("alpha", "alpha_001"):
        pass  # granted, and released on the way out


def test_the_locks_directory_is_created_on_first_use(tmp_path: Path) -> None:
    with FilesystemSessionLock(tmp_path).claim_job("alpha"):
        pass

    assert (tmp_path / "locks").is_dir()


def test_a_running_session_cannot_be_claimed(tmp_path: Path) -> None:
    locks = FilesystemSessionLock(tmp_path)

    with (
        locks.hold_session("alpha", "alpha_001"),
        pytest.raises(SessionRunningError) as caught,
        FilesystemSessionLock(tmp_path).claim_session("alpha", "alpha_001"),
    ):
        pass

    assert caught.value.session == "alpha_001"
    assert caught.value.job == "alpha"


def test_the_claim_succeeds_once_the_session_has_ended(tmp_path: Path) -> None:
    locks = FilesystemSessionLock(tmp_path)

    with locks.hold_session("alpha", "alpha_001"):
        pass

    with FilesystemSessionLock(tmp_path).claim_session("alpha", "alpha_001"):
        pass  # the hold released with its block


def test_a_different_session_of_the_same_job_is_still_claimable(tmp_path: Path) -> None:
    """The point of locking the session rather than the job: siblings stay removable."""
    locks = FilesystemSessionLock(tmp_path)

    with (
        locks.hold_session("alpha", "alpha_001"),
        FilesystemSessionLock(tmp_path).claim_session("alpha", "alpha_002"),
    ):
        pass


def test_a_claim_is_released_even_when_the_block_raises(tmp_path: Path) -> None:
    locks = FilesystemSessionLock(tmp_path)
    message = "the purge failed"

    with pytest.raises(RuntimeError, match=message), locks.claim_session("alpha", "alpha_001"):
        raise RuntimeError(message)

    with FilesystemSessionLock(tmp_path).claim_session("alpha", "alpha_001"):
        pass  # not left held by the raise


@_WINDOWS_HAS_NO_SHARED_MODE
def test_several_sessions_of_one_job_hold_it_at_once(tmp_path: Path) -> None:
    """The shared level: concurrent sessions of one job do not exclude each other."""
    with (
        FilesystemSessionLock(tmp_path).hold_job("alpha"),
        FilesystemSessionLock(tmp_path).hold_job("alpha"),
    ):
        pass


@_WINDOWS_HAS_NO_SHARED_MODE
def test_a_job_with_a_running_session_cannot_be_claimed(tmp_path: Path) -> None:
    locks = FilesystemSessionLock(tmp_path)

    with (
        locks.hold_job("alpha"),
        pytest.raises(JobRunningError) as caught,
        FilesystemSessionLock(tmp_path).claim_job("alpha"),
    ):
        pass

    assert caught.value.job == "alpha"


@_WINDOWS_HAS_NO_SHARED_MODE
def test_another_job_is_unaffected_by_a_running_one(tmp_path: Path) -> None:
    locks = FilesystemSessionLock(tmp_path)

    with locks.hold_job("alpha"), FilesystemSessionLock(tmp_path).claim_job("beta"):
        pass


@_WINDOWS_HAS_NO_SHARED_MODE
def test_a_job_becomes_claimable_once_its_last_session_ends(tmp_path: Path) -> None:
    locks = FilesystemSessionLock(tmp_path)

    with locks.hold_job("alpha"):
        with locks.hold_job("alpha"):
            pass
        # one holder left, so still refused
        with pytest.raises(JobRunningError), FilesystemSessionLock(tmp_path).claim_job("alpha"):
            pass

    with FilesystemSessionLock(tmp_path).claim_job("alpha"):
        pass


def test_claiming_a_job_does_not_claim_its_sessions(tmp_path: Path) -> None:
    """Two independent levels: the job's file is not any session's file."""
    locks = FilesystemSessionLock(tmp_path)

    with (
        locks.claim_job("alpha"),
        FilesystemSessionLock(tmp_path).claim_session("alpha", "alpha_001"),
    ):
        pass


def test_a_session_paired_with_the_wrong_job_locks_something_else(tmp_path: Path) -> None:
    """The job is part of the lock's name, so a mismatched pair cannot claim the session."""
    locks = FilesystemSessionLock(tmp_path)

    with (
        locks.hold_session("alpha", "alpha_001"),
        FilesystemSessionLock(tmp_path).claim_session("beta", "alpha_001"),
    ):
        pass  # granted: it is not the same lock


def test_a_job_name_that_is_not_a_filename_still_locks(tmp_path: Path) -> None:
    """Job names are whatever the user typed; the lock file is a hash, not the name."""
    awkward = "../../etc/passwd"

    with FilesystemSessionLock(tmp_path).claim_job(awkward):
        pass

    assert [path.parent for path in (tmp_path / "locks").iterdir()] == [tmp_path / "locks"]
