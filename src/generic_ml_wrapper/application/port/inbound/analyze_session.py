# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for analysing sessions from their clients' own files."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from generic_ml_wrapper.common.errors import DomainError

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.session_analysis import SessionAnalysis


class NothingToAnalyzeError(DomainError, ValueError):
    """Raised when the target is no gmlw session, job or readable session file."""


class SessionFileUnavailableError(DomainError, ValueError):
    """Raised when a gmlw session has no client file that can be read."""


class AnalyzeSession(ABC):
    """Show what sessions did, from the metadata of their clients' own files."""

    @abstractmethod
    def execute(self, target: str) -> tuple[SessionAnalysis, ...]:
        """Analyse a gmlw session, every session of a job, or one session file.

        Args:
            target: A gmlw session id (``<job>_NNN``), a job, or the path of a client's
                session file (a session run outside gmlw).

        Returns:
            One analysis per session, oldest first. A job's sessions without a readable
            file are left out.

        Raises:
            NothingToAnalyzeError: ``target`` is none of the three.
            SessionFileUnavailableError: The session (or every session of the job) has no
                readable file: its client is not analysable, it never got the client's
                id, or the client no longer has it.
        """
