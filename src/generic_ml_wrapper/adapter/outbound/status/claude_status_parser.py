# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Parse Claude Code's status-line payload into a ``ClientStatus``."""

from __future__ import annotations

from typing import cast

from generic_ml_wrapper.application.domain.model.client_status import ClientStatus
from generic_ml_wrapper.application.port.outbound.client_status import ClientStatusParserPort


def _dig(payload: object, *keys: str) -> object:
    current: object = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = cast("dict[str, object]", current).get(key)
    return current


class ClaudeStatusParser(ClientStatusParserPort):
    """Read model, context fill, and session cost from Claude Code's payload."""

    def parse(self, payload: dict[str, object]) -> ClientStatus:
        """Parse Claude Code's status payload.

        Args:
            payload: The decoded JSON Claude Code pipes to the status-line command
                (``model.display_name``, ``context_window.used_percentage``,
                ``cost.total_cost_usd``, and ``rate_limits`` buckets).

        Returns:
            The parsed status.
        """
        return ClientStatus(
            model=_as_str(_dig(payload, "model", "display_name")),
            context_pct=_as_pct(_dig(payload, "context_window", "used_percentage")),
            session_cost_usd=_as_float(_dig(payload, "cost", "total_cost_usd")),
            extras=_extras(payload),
        )


# Claude reports two rolling allowance windows; each answers "am I burning it?".
_QUOTA_WINDOWS = (("5h", "five_hour"), ("wk", "seven_day"))


def _extras(payload: dict[str, object]) -> tuple[str, ...]:
    """Claude's client-specific status blocks (currently its rate-limit quota)."""
    quota = _quota(_dig(payload, "rate_limits"))
    return (f"quota {quota}",) if quota else ()


def _quota(rate_limits: object) -> str | None:
    parts: list[str] = []
    for label, key in _QUOTA_WINDOWS:
        pct = _as_pct(_dig(rate_limits, key, "used_percentage"))
        if pct is not None:
            parts.append(f"{label} {pct}%")
    return " · ".join(parts) if parts else None


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
