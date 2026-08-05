# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Everything one job holds -- what a delete would take with it."""

from __future__ import annotations

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
