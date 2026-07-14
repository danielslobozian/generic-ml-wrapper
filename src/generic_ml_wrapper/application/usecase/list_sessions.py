# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListSessions use case: summarise a job's recorded sessions."""

from __future__ import annotations

from generic_ml_wrapper.application.port.inbound.list_sessions import ListSessions, SessionSummary
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort


class ListSessionsUseCase(ListSessions):
    """Summarise the sessions recorded for a job."""

    def __init__(self, store: SessionStorePort) -> None:
        """Wire the use case to the session store.

        Args:
            store: Where the job's sessions are read from.
        """
        self._store = store

    def execute(self, job: str) -> list[SessionSummary]:
        """List a job's sessions.

        Args:
            job: The job identifier.

        Returns:
            One summary per session, oldest first.
        """
        return [
            SessionSummary(session_id=session.session_id, client=session.client)
            for session in self._store.sessions_for_job(job)
        ]
