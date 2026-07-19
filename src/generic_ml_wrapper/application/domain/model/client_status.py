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
        context_window_size: The context window's maximum size in tokens, or
            ``None``. Reported alongside the fill so the renderer can show the
            denominator (``155.6k/200k``) rather than a bare percentage.
        context_tokens: The tokens currently in the window (input + cache), or
            ``None``. May exceed ``context_window_size`` when the client under-
            reports the window (e.g. behind a gateway), so it is not clamped to it.
    """

    model: str | None
    context_pct: int | None
    session_cost_usd: float | None
    extras: tuple[str, ...]
    context_window_size: int | None = None
    context_tokens: int | None = None

    def __post_init__(self) -> None:
        """Reject an out-of-range context percentage, a negative cost, or negative tokens."""
        if self.context_pct is not None and not 0 <= self.context_pct <= _MAX_CONTEXT_PCT:
            message = f"context_pct must be within 0..100, got {self.context_pct}"
            raise ValueError(message)
        if self.session_cost_usd is not None and (
            self.session_cost_usd < 0 or not math.isfinite(self.session_cost_usd)
        ):
            message = f"session_cost_usd must be >= 0 and finite, got {self.session_cost_usd}"
            raise ValueError(message)
        if self.context_window_size is not None and self.context_window_size < 0:
            message = f"context_window_size must be >= 0, got {self.context_window_size}"
            raise ValueError(message)
        if self.context_tokens is not None and self.context_tokens < 0:
            message = f"context_tokens must be >= 0, got {self.context_tokens}"
            raise ValueError(message)
