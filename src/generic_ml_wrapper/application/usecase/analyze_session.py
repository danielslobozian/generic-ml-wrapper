# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The AnalyzeSession use case: find a session's client file, and analyse it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.service.session_analyzer import analyze
from generic_ml_wrapper.application.port.inbound.analyze_session import (
    AnalyzeSession,
    NothingToAnalyzeError,
    RecentSession,
    SessionFileUnavailableError,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.session import Session
    from generic_ml_wrapper.application.domain.model.session_analysis import SessionAnalysis
    from generic_ml_wrapper.application.port.outbound.session_files import SessionFilesPort
    from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort


class AnalyzeSessionUseCase(AnalyzeSession):
    """Resolve a session, a job or a file to client session files, and analyse each."""

    def __init__(self, store: SessionStorePort, files: SessionFilesPort) -> None:
        """Wire the use case to the recorded sessions and the clients' files.

        Args:
            store: Where gmlw's jobs and sessions are read from.
            files: Where the clients' own session files are found and read.
        """
        self._store = store
        self._files = files

    def execute(self, target: str) -> tuple[SessionAnalysis, ...]:
        """Analyse a gmlw session, every session of a job, or one session file."""
        session = self._session(target)
        if session is not None:
            return (self._analysis(session),)
        if target in self._store.jobs():
            return self._job(target)
        record = self._files.read(target)
        if record is None:
            raise NothingToAnalyzeError("analyze.error.nothing", target=target)
        return (analyze(record),)

    def recent(self, limit: int = 30) -> tuple[RecentSession, ...]:
        """The latest session files, each with the gmlw session that ran it, if any."""
        by_uuid = {
            (session.client, session.uuid): session.session_id
            for job in self._store.jobs()
            for session in self._store.sessions_for_job(job)
            if session.uuid is not None
        }
        return tuple(
            RecentSession(
                found, None if found.uuid is None else by_uuid.get((found.client, found.uuid))
            )
            for found in self._files.recent(limit)
        )

    def _session(self, target: str) -> Session | None:
        """The gmlw session named ``target``, or ``None`` when it names none."""
        job, separator, _ = target.rpartition("_")
        if not separator:
            return None
        return next((s for s in self._store.sessions_for_job(job) if s.session_id == target), None)

    def _job(self, job: str) -> tuple[SessionAnalysis, ...]:
        """Every session of ``job`` that has a readable file, oldest first."""
        analyses: list[SessionAnalysis] = []
        for session in self._store.sessions_for_job(job):
            try:
                analyses.append(self._analysis(session))
            except SessionFileUnavailableError:
                continue
        if not analyses:
            raise SessionFileUnavailableError("analyze.error.job_unavailable", job=job)
        return tuple(analyses)

    def _analysis(self, session: Session) -> SessionAnalysis:
        """Analyse one gmlw session from its client's file."""
        if session.client not in self._files.analyzable_clients():
            raise SessionFileUnavailableError(
                "analyze.error.client", session=session.session_id, client=session.client
            )
        source = None if session.uuid is None else self._files.locate(session.client, session.uuid)
        record = None if source is None else self._files.read(source)
        if record is None:
            raise SessionFileUnavailableError("analyze.error.missing", session=session.session_id)
        return analyze(record, session.session_id)
