# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for removing recorded sessions from a job."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from generic_ml_wrapper.application.port.inbound.session_footprint import SessionFootprint


class DeleteSessionsUseCase(ABC):
    """Remove recorded sessions from a job, with their usage and their files."""

    @abstractmethod
    def preview(self, job: str, sessions: Sequence[str]) -> list[SessionFootprint]:
        """Report what deleting these sessions would remove, without removing it.

        Args:
            job: The job the sessions belong to.
            sessions: The session ids to measure, in the order given.

        Returns:
            One footprint per session, in the order given.

        Raises:
            NoSuchJobError: If the job has no recorded activity.
            NoSuchSessionError: If any session is not recorded for the job.
        """

    @abstractmethod
    def execute(self, job: str, sessions: Sequence[str]) -> list[SessionFootprint]:
        """Delete the sessions, their recorded usage, and their files.

        The whole batch is validated before anything is removed: one unknown id leaves
        every other session untouched, rather than deleting half the request and then
        failing on the rest.

        Args:
            job: The job the sessions belong to.
            sessions: The session ids to delete, in the order given.

        Returns:
            One footprint per deleted session -- what was actually removed.

        Raises:
            NoSuchJobError: If the job has no recorded activity.
            NoSuchSessionError: If any session is not recorded for the job.
        """
