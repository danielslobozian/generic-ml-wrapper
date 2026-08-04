# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The SessionCost value object: one session's cumulative cost, as reported."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionCost:
    """The cumulative cost a client reported for one of its sessions.

    The counterpart to :class:`~generic_ml_wrapper.application.domain.model.turn_usage.TurnUsage`
    for the shallower of the two measurements. A turn is what the metering gateway saw on
    the wire; this is the running total the client itself reports through its status
    payload, one figure per session, replaced as it grows.

    It exists so the store's port takes a value that has already been checked rather than
    a bare number. Guarding the boundary in the type is the only guard there is: the
    schema carries no ``CHECK`` constraints, deliberately, because protecting the data is
    the domain's responsibility and a store reached around rather than through it fails on
    the way back in, when the domain loads what was written.

    Attributes:
        session_id: The session the total belongs to.
        cost_usd: The cumulative cost in USD.
    """

    session_id: str
    cost_usd: float

    def __post_init__(self) -> None:
        """Reject an unusable total: no session to attribute it to, or an impossible amount."""
        if not self.session_id:
            message = "session_id must not be empty"
            raise ValueError(message)
        if self.cost_usd < 0 or not math.isfinite(self.cost_usd):
            message = f"cost_usd must be a non-negative finite number, got {self.cost_usd}"
            raise ValueError(message)
