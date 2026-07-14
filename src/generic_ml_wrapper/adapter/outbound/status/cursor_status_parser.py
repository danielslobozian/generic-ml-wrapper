# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Parse cursor-agent's status-line payload into a ``ClientStatus``."""

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


class CursorStatusParser(ClientStatusParserPort):
    """Read model and context fill from cursor-agent's status payload.

    cursor-agent pipes a Claude-Code-compatible payload, so ``model.display_name``
    and ``context_window.used_percentage`` parse just like Claude's. cursor is
    subscription-metered, so there is no per-session cost on the wire (``None``).

    Its allowance block -- the plan pools (auto/api %) -- is NOT in the status
    payload; cursor exposes that only via its dashboard API. ``extras`` therefore
    carries the plan block only if a payload happens to include a ``plan`` table;
    otherwise it is omitted (the dashboard-API fetch is a separate concern).
    """

    def parse(self, payload: dict[str, object]) -> ClientStatus:
        """Parse cursor-agent's status payload.

        Args:
            payload: The decoded JSON cursor-agent pipes to the status-line command
                (``model.display_name``, ``context_window.used_percentage``, and --
                if present -- a ``plan`` table).

        Returns:
            The parsed status.
        """
        return ClientStatus(
            model=_as_str(_dig(payload, "model", "display_name")),
            context_pct=_as_pct(_dig(payload, "context_window", "used_percentage")),
            session_cost_usd=None,
            extras=_plan_extras(_dig(payload, "plan")),
        )


def _plan_extras(plan: object) -> tuple[str, ...]:
    """Cursor's plan-pool allowance block, if the payload carries one (auto/api %)."""
    parts: list[str] = []
    for label, key in (("auto", "auto_pct"), ("api", "api_pct")):
        pct = _as_pct(_dig(plan, key))
        if pct is not None:
            parts.append(f"{label} {pct}%")
    return (f"plan {' · '.join(parts)}",) if parts else ()


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _as_pct(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(value)
