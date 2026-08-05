# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListSessionsUseCase use case: summarise a job's recorded sessions."""

from __future__ import annotations

from generic_ml_wrapper.application.port.inbound.list_sessions import ListSessionsUseCase
from generic_ml_wrapper.application.port.inbound.session_summary import SessionSummary
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort


class ListSessionsService(ListSessionsUseCase):
    """Summarise the sessions recorded for a job, with what each one used."""

    def __init__(
        self, store: SessionStorePort, turns: PerTurnMeteringPort, usage: UsageStorePort
    ) -> None:
        """Wire the use case to the session store and the two usage stores.

        A session is recorded before its client runs, so one abandoned at the prompt is
        recorded exactly like one that did a day's work. Carrying the turn count and cost
        is what tells them apart in a listing -- and what makes deleting the empty one an
        informed choice rather than a guess.

        Args:
            store: Where the job's sessions are read from.
            turns: Where metered turns are read from.
            usage: Where recorded session costs are read from.
        """
        self._store = store
        self._turns = turns
        self._usage = usage

    def execute(self, job: str) -> list[SessionSummary]:
        """List a job's sessions.

        Args:
            job: The job identifier.

        Returns:
            One summary per session, oldest first.
        """
        # Both usage stores are read per job, once, rather than per session: the listing
        # is a hot-ish path (it also feeds the TUI's pickers) and the alternative is one
        # query per row.
        turns_per_session: dict[str, int] = {}
        for turn in self._turns.turns_for_job(job):
            turns_per_session[turn.session_id] = turns_per_session.get(turn.session_id, 0) + 1
        costs = self._usage.session_costs(job)
        return [
            SessionSummary(
                session_id=session.session_id,
                client=session.client,
                cwd=session.cwd,
                resumable=session.resumable,
                created_at=session.created_at,
                turn_count=turns_per_session.get(session.session_id, 0),
                cost_usd=costs.get(session.session_id, 0.0),
            )
            for session in self._store.sessions_for_job(job)
        ]
