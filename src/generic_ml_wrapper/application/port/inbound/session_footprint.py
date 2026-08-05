# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Everything one session holds -- what a delete would take with it."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionFootprint:
    """Everything one session holds -- what a delete would take with it.

    Shown before a delete is confirmed, and returned after one, so "what will go" and
    "what went" are the same shape rather than two descriptions that can disagree.

    Attributes:
        job: The job the session belongs to.
        session: The session's ``<job>_NNN`` id.
        turns: Metered turns recorded for it (``0`` for a session abandoned before its
            first turn -- the case a delete most often exists for).
        cost_usd: Its recorded cumulative cost.
        contexts: Compiled-context files it holds (0 or 1).
        transcript_calls: Transcript files it holds (``0`` unless transcripts were on).
        removed: Whether it actually went. ``True`` on a preview, where it means "this is
            what would go"; on a result it is the receipt, and ``False`` says the session
            is still there -- its files could not be removed, so its rows were left alone
            and the same delete can simply be asked for again.
    """

    job: str
    session: str
    turns: int
    cost_usd: float
    contexts: int
    transcript_calls: int
    removed: bool = True
