# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for persisting and reading sessions."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.domain.model.session import Session


class SessionStorePort(ABC):
    """Persist and read the sessions recorded for a job."""

    @abstractmethod
    def jobs(self) -> list[str]:
        """Return the ids of all jobs that have recorded sessions.

        Returns:
            The job ids, sorted (empty if nothing has been recorded).
        """

    @abstractmethod
    def record(self, session: Session) -> None:
        """Append a session to its job's record.

        Args:
            session: The session to persist.
        """

    @abstractmethod
    def sessions_for_job(self, job: str) -> list[Session]:
        """Return the sessions recorded for a job, oldest first.

        Args:
            job: The job identifier.

        Returns:
            The sessions, oldest first (empty if the job is unknown).
        """

    @abstractmethod
    def ids_for_job(self, job: str) -> list[str]:
        """Return the session ids recorded for a job, oldest first.

        Args:
            job: The job identifier.

        Returns:
            The session ids, oldest first (empty if the job is unknown).
        """

    @abstractmethod
    def latest_for_job(self, job: str) -> Session | None:
        """Return the most recently recorded session for a job.

        Args:
            job: The job identifier.

        Returns:
            The latest session, or ``None`` if the job has none.
        """
