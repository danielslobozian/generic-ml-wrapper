# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The TurnUsage value object: one metered request/response round."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TurnUsage:
    """The token (and optional cost) usage of a single client turn.

    A turn is one request/response round a metering gateway observed on the wire.

    Attributes:
        session_id: The session the turn belongs to.
        input_tokens: Prompt tokens sent upstream.
        output_tokens: Completion tokens received.
        cost_usd: The turn's cost in USD when the gateway can compute it, else
            ``None`` (e.g. no price is known for the model).
        model: The model that served the turn, or ``None`` if unreported.
        cache_creation_tokens: Prompt tokens written to the cache this turn.
        cache_read_tokens: Prompt tokens served from the cache this turn.
        timestamp: The turn's wall-clock time (epoch seconds), or ``0.0``.
        duration_s: How long the turn took, in seconds, or ``0.0``.
        turn_id: The provider's id for this turn, or ``None``.
    """

    session_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    model: str | None
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    timestamp: float = 0.0
    duration_s: float = 0.0
    turn_id: str | None = None

    def __post_init__(self) -> None:
        """Reject impossible usage: negative counts, or non-finite/negative amounts."""
        for name in (
            "input_tokens",
            "output_tokens",
            "cache_creation_tokens",
            "cache_read_tokens",
        ):
            value: int = getattr(self, name)
            if value < 0:
                message = f"{name} must be non-negative, got {value}"
                raise ValueError(message)
        if self.cost_usd is not None and (self.cost_usd < 0 or not math.isfinite(self.cost_usd)):
            message = f"cost_usd must be a non-negative finite number, got {self.cost_usd}"
            raise ValueError(message)
        if self.timestamp < 0 or not math.isfinite(self.timestamp):
            message = f"timestamp must be a non-negative finite number, got {self.timestamp}"
            raise ValueError(message)
        if self.duration_s < 0 or not math.isfinite(self.duration_s):
            message = f"duration_s must be a non-negative finite number, got {self.duration_s}"
            raise ValueError(message)
