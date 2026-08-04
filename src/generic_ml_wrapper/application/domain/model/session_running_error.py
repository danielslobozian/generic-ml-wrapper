# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The error raised when a session cannot be removed because it is running."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.domain_error import DomainError


class SessionRunningError(DomainError, RuntimeError):
    """The session has a live client and must not be removed under it.

    Removing a session whose client is still going leaves that client writing turns and
    costs against rows that no longer exist. Refusing is the only answer that does not
    ask the user to notice the collision themselves -- and it is refused immediately
    rather than waited out, because the wait would be however long the person keeps
    working.
    """

    def __init__(self, job: str, session: str) -> None:
        """Name the session that is running.

        Args:
            job: The job the session belongs to.
            session: The session's ``<job>_NNN`` id.
        """
        self.job = job
        self.session = session
        super().__init__("error.session.running", job=job, session=session)
