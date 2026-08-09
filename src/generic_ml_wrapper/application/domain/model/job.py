# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A job and the sessions recorded against it."""

from __future__ import annotations

from dataclasses import dataclass, field

from generic_ml_wrapper.application.domain.model.job_id import JobId
from generic_ml_wrapper.application.domain.model.no_such_session_error import NoSuchSessionError
from generic_ml_wrapper.application.domain.model.session import Session


@dataclass(frozen=True)
class Job:
    """A job and the sessions recorded against it.

    Attributes:
        job_id: The validated identifier the sessions are filed under.
        sessions: Every recorded session, oldest first, in the order the store returned
            them. The order is the contract: ``latest_session`` is the last element, and
            nothing re-derives it from a timestamp or from the session name.
    """

    job_id: JobId
    sessions: tuple[Session, ...] = field(default_factory=tuple)

    def session_for(self, session_id: str) -> Session:
        """Return the session with this id.

        Args:
            session_id: The human-readable id, as the user typed or picked it.

        Returns:
            The matching session.

        Raises:
            NoSuchSessionError: When this job has no session with that id — never a
                fresh session, so a mistyped id is refused rather than quietly replaced.
        """
        for session in self.sessions:
            if session.session_id == session_id:
                return session
        raise NoSuchSessionError(
            "error.session.not_found", session=session_id, job=str(self.job_id)
        )

    def latest_session(self) -> Session:
        """Return the most recently recorded session.

        Returns:
            The last of ``sessions`` — the one recorded most recently, whatever has
            happened in the others since.

        Raises:
            NoSuchSessionError: When nothing has run on this job yet, which a job
                created ahead of its first session legitimately is.
        """
        if not self.sessions:
            raise NoSuchSessionError("error.session.none_yet", job=str(self.job_id))
        return self.sessions[-1]
