# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for removing a job's or a session's recorded rows."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LedgerPurgePort(ABC):
    """Remove the recorded rows of a session, or of a whole job.

    Deliberately its own port rather than a ``delete`` on the session/usage/metering
    stores. Those three are append-and-read contracts with in-memory reference fakes
    (``tests/_conformance.py``); a destructive method on each would spread one operation
    across three of them and leave a removal that could half-apply. Here it is one
    abstraction with one implementation, free to make each purge a single transaction.

    Counting is not this port's job: the existing read ports already report what a job
    or session holds, so a purge only has to remove.
    """

    @abstractmethod
    def purge_session(self, job: str, session: str) -> None:
        """Remove one session's rows: the session itself, its turns, and its cost.

        The job's own row is left in place -- a job outlives the sessions removed from
        it, and is only removed by :meth:`purge_job`.

        Args:
            job: The job the session belongs to.
            session: The session's ``<job>_NNN`` id.
        """

    @abstractmethod
    def purge_job(self, job: str) -> None:
        """Remove a job and every row recorded under it.

        Args:
            job: The job to remove.
        """
