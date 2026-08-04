# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for removing whole jobs and everything recorded under them."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class JobFootprint:
    """Everything one job holds -- what a delete would take with it.

    The same shape as a :class:`~generic_ml_wrapper.application.port.inbound
    .delete_sessions.SessionFootprint`, one level up: a job's footprint is the fold of
    its sessions' footprints, plus the job's own row.

    Attributes:
        job: The job identifier.
        sessions: How many sessions are recorded for it.
        turns: Metered turns across all of them.
        cost_usd: Their combined recorded cost.
        contexts: Compiled-context files the job holds.
        transcript_calls: Transcript files the job holds (``0`` unless transcripts
            were on).
        removed: Whether it actually went. ``True`` on a preview, where it means "this is
            what would go"; on a result it is the receipt, and ``False`` says the job is
            still there -- its files could not be removed, so its rows were left alone and
            the same delete can simply be asked for again.
    """

    job: str
    sessions: int
    turns: int
    cost_usd: float
    contexts: int
    transcript_calls: int
    removed: bool = True


class DeleteJobs(ABC):
    """Remove whole jobs: their sessions, their usage, and their files."""

    @abstractmethod
    def preview(self, jobs: Sequence[str]) -> list[JobFootprint]:
        """Report what deleting these jobs would remove, without removing it.

        Args:
            jobs: The job ids to measure, in the order given.

        Returns:
            One footprint per job, in the order given.

        Raises:
            NoSuchJobError: If any job has no recorded activity.
        """

    @abstractmethod
    def execute(self, jobs: Sequence[str]) -> list[JobFootprint]:
        """Delete the jobs, their sessions, their recorded usage, and their files.

        The whole batch is validated before anything is removed: one unknown id leaves
        every other job untouched.

        Args:
            jobs: The job ids to delete, in the order given.

        Returns:
            One footprint per deleted job -- what was actually removed.

        Raises:
            NoSuchJobError: If any job has no recorded activity.
        """
