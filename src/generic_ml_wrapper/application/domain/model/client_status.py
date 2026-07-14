# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ClientStatus value object: what a client reports to its status line."""

from __future__ import annotations

import math
from dataclasses import dataclass

_MAX_CONTEXT_PCT = 100


@dataclass(frozen=True)
class ClientStatus:
    """A client's live status, parsed from the payload it pipes to the status line.

    Each field is optional because a client may not report it (or not yet).

    Attributes:
        model: The active model's display name, or ``None``.
        context_pct: The context-window fill percentage, or ``None``.
        session_cost_usd: The session's cumulative cost in USD, or ``None``.
        extras: Client-specific, already-formatted status blocks (e.g. Claude's
            quota) placed after the common fields; empty when the client reports
            none. Each block carries its own label because its shape and name vary
            by client, so the parser owns the formatting and the renderer only
            places them.
    """

    model: str | None
    context_pct: int | None
    session_cost_usd: float | None
    extras: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject an out-of-range context percentage or a negative cost."""
        if self.context_pct is not None and not 0 <= self.context_pct <= _MAX_CONTEXT_PCT:
            message = f"context_pct must be within 0..100, got {self.context_pct}"
            raise ValueError(message)
        if self.session_cost_usd is not None and (
            self.session_cost_usd < 0 or not math.isfinite(self.session_cost_usd)
        ):
            message = f"session_cost_usd must be >= 0 and finite, got {self.session_cost_usd}"
            raise ValueError(message)
