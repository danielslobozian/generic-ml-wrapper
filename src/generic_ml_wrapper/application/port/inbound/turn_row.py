# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""One metered turn, for the per-turn table."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnRow:
    """One metered turn, for the per-turn table.

    Attributes:
        timestamp: The turn's wall-clock time (epoch seconds), or ``0.0``.
        model: The model that served the turn.
        duration_s: How long the turn took, in seconds.
        input_tokens: Fresh prompt tokens.
        output_tokens: Completion tokens.
        cache_tokens: Cache creation + read prompt tokens.
        turn_id: The provider's id for the turn, or ``None``.
    """

    timestamp: float
    model: str
    duration_s: float
    input_tokens: int
    output_tokens: int
    cache_tokens: int
    turn_id: str | None
