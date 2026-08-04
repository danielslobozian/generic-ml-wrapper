# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A whole-store exclusive lock, held by the operating system.

OS-level file locking (``fcntl.flock`` on Unix and macOS, ``msvcrt.locking`` on
Windows). The lock belongs to the process, so it is released when the process exits or
crashes -- there is no stale lock file to clean up afterwards, which is the failure mode
a hand-rolled lock file always has.

Only one mode exists here, and only one caller needs it: migration waits for any other
holder to finish rather than failing. Two ``gmlw`` commands starting against a brand-new
ledger would otherwise race to create the same tables; with this, the second waits, then
finds the store already current and does nothing. On Windows ``LK_LOCK`` retries for
about ten seconds before giving up, which is that platform's nearest equivalent to
waiting.
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

_FILENAME = "store.lock"


class FilesystemStoreLock:
    """An exclusive lock over ``<store>/store.lock``, taken by waiting."""

    def __init__(self, store_root: Path) -> None:
        """Bind the lock to the directory holding the store.

        Args:
            store_root: The directory the lock file lives in (created if absent).
        """
        self._path = store_root / _FILENAME

    @contextmanager
    def acquire_exclusive_blocking(self) -> Generator[None]:
        """Hold the store exclusively, waiting for any current holder to release.

        Yields:
            Nothing; the lock is held for the duration of the block.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(str(self._path), os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            _lock_exclusive_blocking(descriptor)
        except OSError:
            os.close(descriptor)
            raise
        try:
            yield
        finally:
            _unlock(descriptor)
            os.close(descriptor)


def _lock_exclusive_blocking(descriptor: int) -> None:
    """Take the lock, blocking until it is free."""
    if sys.platform == "win32":
        import msvcrt  # noqa: PLC0415  (platform-only: importing it on Unix fails)

        msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
    else:
        import fcntl  # noqa: PLC0415  (platform-only: importing it on Windows fails)

        fcntl.flock(descriptor, fcntl.LOCK_EX)


def _unlock(descriptor: int) -> None:
    """Release the lock."""
    if sys.platform == "win32":
        import msvcrt  # noqa: PLC0415  (platform-only: importing it on Unix fails)

        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl  # noqa: PLC0415  (platform-only: importing it on Windows fails)

        fcntl.flock(descriptor, fcntl.LOCK_UN)
