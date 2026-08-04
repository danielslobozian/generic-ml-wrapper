# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for marking a session as running, and refusing to remove one.

Two levels, because a job can have several sessions running at once. A running session
holds an **exclusive** lock on itself and a **shared** lock on its job, for as long as
its client lives. Removal takes the matching lock the other way round:

- deleting one session claims that session exclusively, so a *different*, stopped session
  of the same job is still removable;
- deleting a whole job claims the job exclusively, which no shared holder allows -- so it
  refuses while any of its sessions runs, without listing them and without a gap in which
  a new one could start.

The claims are **fail-fast**. Waiting would be wrong here: the thing being waited for is
a person's session, which may run for hours, and a delete that eventually succeeds is not
what a user who was told "that is running" expects. This is the one behaviour deliberately
*not* borrowed from the cache's per-key lock, which waits and then proceeds anyway so that
a hung peer never blocks a call -- proceeding anyway is exactly the outcome to prevent.

An implementation must release its locks when the holding process dies, without anything
having to clean up. A session ended by a crash, a closed laptop or ``kill -9`` must leave
its job deletable; a marker that outlives its process would make a job undeletable
forever after one crash, and the remedy would be telling a user which file to delete.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager


class SessionLockPort(ABC):
    """Mark sessions as running, and claim them exclusively in order to remove them."""

    @abstractmethod
    def hold_session(self, job: str, session_id: str) -> AbstractContextManager[None]:
        """Mark one session as running for the duration of the block.

        Args:
            job: The job the session belongs to.
            session_id: The session's ``<job>_NNN`` id.

        Returns:
            A context manager holding the session's exclusive lock.
        """

    @abstractmethod
    def hold_job(self, job: str) -> AbstractContextManager[None]:
        """Mark a job as having a running session, alongside any others, for the block.

        Shared: several sessions of one job hold this at the same time.

        Args:
            job: The job one of whose sessions is running.

        Returns:
            A context manager holding the job's shared lock.
        """

    @abstractmethod
    def claim_session(self, job: str, session_id: str) -> AbstractContextManager[None]:
        """Take one session exclusively so it can be removed, or refuse at once.

        Held across the whole removal -- the ledger rows and the files both -- so nothing
        can start under a delete already in progress.

        Args:
            job: The job the session belongs to.
            session_id: The session's ``<job>_NNN`` id.

        Returns:
            A context manager holding the session's exclusive lock.

        Raises:
            SessionRunningError: If the session is running.
        """

    @abstractmethod
    def claim_job(self, job: str) -> AbstractContextManager[None]:
        """Take a whole job exclusively so it can be removed, or refuse at once.

        Refused while any of the job's sessions holds the shared lock.

        Args:
            job: The job being removed.

        Returns:
            A context manager holding the job's exclusive lock.

        Raises:
            JobRunningError: If any of the job's sessions is running.
        """
