# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``SessionLockPort`` over lock files the operating system owns.

One file per lockable name under ``<home>/locks/``: a job's file, and a file per session.
``fcntl.flock`` on Unix and macOS, ``msvcrt.locking`` on Windows -- the same machinery as
:mod:`.filesystem_store_lock`, which is why there is no new dependency for any of this.

The property the whole design rests on is that these locks belong to the *process*, not
to the file. When a session's process exits -- cleanly, by crash, or by ``kill -9`` -- the
operating system drops its locks, and the job is deletable again with nothing to clean up.
A hand-written "is there a file called running.lock" would survive the crash and make the
job undeletable until someone was told which file to remove by hand.

Shared locking is an ``fcntl`` capability. ``msvcrt`` has no shared mode, so on Windows
the job-level shared hold is a documented no-op: a job delete there is not refused by a
running session, though deleting that session directly still is. The wrapper's second
platform, a single-user local tool, and the same trade the cache made for the same reason.
"""

from __future__ import annotations

import hashlib
import os
import sys
from contextlib import contextmanager, suppress
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.job_running_error import JobRunningError
from generic_ml_wrapper.application.domain.model.session_running_error import SessionRunningError
from generic_ml_wrapper.application.port.outbound.session_lock import SessionLockPort

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

_LOCKS_DIRNAME = "locks"


class FilesystemSessionLockAdapter(SessionLockPort):
    """Session and job locks over ``<home>/locks/*.lock``, held by the operating system."""

    def __init__(self, home: Path) -> None:
        """Bind the locks to the directory they live under.

        Args:
            home: The wrapper's home directory; ``locks/`` is created inside it on use.
        """
        self._locks_dir = home / _LOCKS_DIRNAME

    @contextmanager
    def hold_session(self, job: str, session_id: str) -> Generator[None]:
        """Hold one session exclusively for as long as its client runs."""
        with self._locked(self._session_name(job, session_id), exclusive=True, blocking=True):
            yield

    @contextmanager
    def hold_job(self, job: str) -> Generator[None]:
        """Hold the job alongside its other running sessions, for as long as this one runs."""
        with self._locked(self._job_name(job), exclusive=False, blocking=True):
            yield

    @contextmanager
    def claim_session(self, job: str, session_id: str) -> Generator[None]:
        """Take one session exclusively, refusing at once if its client is running.

        Raises:
            SessionRunningError: If the session is running.
        """
        try:
            with self._locked(self._session_name(job, session_id), exclusive=True, blocking=False):
                yield
        except BlockingIOError as error:
            raise SessionRunningError(job, session_id) from error

    @contextmanager
    def claim_job(self, job: str) -> Generator[None]:
        """Take the whole job exclusively, refusing at once if any session is running.

        Raises:
            JobRunningError: If any of the job's sessions is running.
        """
        try:
            with self._locked(self._job_name(job), exclusive=True, blocking=False):
                yield
        except BlockingIOError as error:
            raise JobRunningError(job) from error

    def _job_name(self, job: str) -> str:
        return f"job-{job}"

    def _session_name(self, job: str, session_id: str) -> str:
        # The job is part of the name as well as the session id. The id is unique across
        # the ledger, so this is not needed to tell two sessions apart -- it is here so a
        # caller that pairs a session with the wrong job locks something that is not the
        # session it named, and finds it free, rather than silently claiming a stranger's.
        return f"session-{job}/{session_id}"

    def _path(self, name: str) -> Path:
        # Hashed for the same reason the cache hashes its keys: a job name is whatever the
        # user typed, and a name that is meaningful to a person is not necessarily one a
        # filesystem will accept or keep distinct.
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
        return self._locks_dir / f"{digest}.lock"

    @contextmanager
    def _locked(self, name: str, *, exclusive: bool, blocking: bool) -> Generator[None]:
        """Hold ``name``'s lock file for the block.

        Raises:
            BlockingIOError: If ``blocking`` is false and another process holds it.
        """
        self._locks_dir.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(str(self._path(name)), os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            _lock(descriptor, exclusive=exclusive, blocking=blocking)
        except BaseException:
            os.close(descriptor)
            raise
        try:
            yield
        finally:
            _unlock(descriptor)
            os.close(descriptor)


def _lock(descriptor: int, *, exclusive: bool, blocking: bool) -> None:
    """Take the OS lock, raising ``BlockingIOError`` when a non-blocking take is refused."""
    if sys.platform == "win32":
        import msvcrt  # noqa: PLC0415  (platform-only: importing it on Unix fails)

        if not exclusive:
            return  # msvcrt has no shared mode; documented no-op (see the module docstring)
        mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
        try:
            msvcrt.locking(descriptor, mode, 1)
        except OSError as error:
            # msvcrt reports a refused lock as a plain OSError; the callers above are
            # written against the Unix spelling, so it is normalised here.
            raise BlockingIOError(str(error)) from error
        return
    import fcntl  # noqa: PLC0415  (platform-only: importing it on Windows fails)

    operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    if not blocking:
        operation |= fcntl.LOCK_NB
    fcntl.flock(descriptor, operation)


def _unlock(descriptor: int) -> None:
    """Release the lock."""
    if sys.platform == "win32":
        import msvcrt  # noqa: PLC0415  (platform-only: importing it on Unix fails)

        # A shared hold was a no-op on this platform, so there may be nothing to release.
        with suppress(OSError):
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        return
    import fcntl  # noqa: PLC0415  (platform-only: importing it on Windows fails)

    fcntl.flock(descriptor, fcntl.LOCK_UN)
