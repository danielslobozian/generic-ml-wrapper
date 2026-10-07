# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Parse Claude Code's status-line payload into a ``ClientStatus``."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast

from generic_ml_wrapper.application.domain.model.client_status import ClientStatus
from generic_ml_wrapper.application.port.outbound.client_status import ClientStatusParserPort

if TYPE_CHECKING:
    from collections.abc import Callable


def _dig(payload: object, *keys: str) -> object:
    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = cast("dict[str, object]", current).get(key)
    return current


class ClaudeStatusParser(ClientStatusParserPort):
    """Read model, context fill, and session cost from Claude Code's payload."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        """Wire the parser to a clock.

        Args:
            clock: A source of the current epoch time in seconds, used to render a
                rate-limit window's reset as a relative duration. Injected so the
                quota formatting stays deterministic under test; defaults to the
                wall clock.
        """
        self._clock = clock

    def parse(self, payload: dict[str, object]) -> ClientStatus:
        """Parse Claude Code's status payload.

        Args:
            payload: The decoded JSON Claude Code pipes to the status-line command
                (``model.display_name``, ``context_window`` fill/size/tokens,
                ``cost.total_cost_usd``, and ``rate_limits`` buckets).

        Returns:
            The parsed status.
        """
        return ClientStatus(
            model=_as_str(_dig(payload, "model", "display_name")),
            context_pct=_as_pct(_dig(payload, "context_window", "used_percentage")),
            session_cost_usd=_as_float(_dig(payload, "cost", "total_cost_usd")),
            extras=self._extras(payload),
            context_window_size=_as_int(_dig(payload, "context_window", "context_window_size")),
            context_tokens=_as_int(_dig(payload, "context_window", "total_input_tokens")),
        )

    def _extras(self, payload: dict[str, object]) -> tuple[str, ...]:
        """Claude's client-specific status blocks (currently its rate-limit quota)."""
        quota = self._quota(_dig(payload, "rate_limits"))
        return (f"quota {quota}",) if quota else ()

    def _quota(self, rate_limits: object) -> str | None:
        parts: list[str] = []
        for label, key in _QUOTA_WINDOWS:
            pct = _as_pct(_dig(rate_limits, key, "used_percentage"))
            if pct is None:
                continue
            reset = self._reset_in(_dig(rate_limits, key, "resets_at"))
            parts.append(f"{label} {pct}% ({reset})" if reset else f"{label} {pct}%")
        return " · ".join(parts) if parts else None

    def _reset_in(self, resets_at: object) -> str | None:
        """Render a window's ``resets_at`` epoch as a relative ``↻ 12m`` marker.

        Absent or non-numeric ``resets_at`` yields ``None`` (the window renders as
        percentage only), so a client that omits the reset degrades cleanly.
        """
        if isinstance(resets_at, bool) or not isinstance(resets_at, (int, float)):
            return None
        remaining = int(resets_at - self._clock())
        return f"↻ {_duration(remaining)}"


# Claude reports two rolling allowance windows; each answers "am I burning it?".
_QUOTA_WINDOWS = (("5h", "five_hour"), ("wk", "seven_day"))

_MINUTE = 60
_HOUR = 3600
_DAY = 86400


def _duration(seconds: int) -> str:
    """A coarse relative duration: minutes under an hour, hours under a day, else days."""
    if seconds < _MINUTE:
        return "0m"
    if seconds < _HOUR:
        return f"{seconds // _MINUTE}m"
    if seconds < _DAY:
        return f"{seconds // _HOUR}h"
    return f"{seconds // _DAY}d"


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _as_pct(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(value)


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)
