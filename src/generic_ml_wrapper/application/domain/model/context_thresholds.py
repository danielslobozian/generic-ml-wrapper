# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""How full a context may get before the status line warns about it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_status import ClientStatus


class ContextLevel(StrEnum):
    """How much a context's fill should worry the user.

    Attributes:
        OK: Nothing to say.
        WARN: Worth watching: compaction is getting near, or the context is long.
        ALERT: Time to compact, restart or split the work.
    """

    OK = "ok"
    WARN = "warn"
    ALERT = "alert"


@dataclass(frozen=True)
class ContextThresholds:
    """The fills that raise a context to :attr:`ContextLevel.WARN` and :attr:`ContextLevel.ALERT`.

    Two rules, because they answer different questions. The percentage of the window says
    how near compaction or the hard limit is. The size in tokens says how long the context
    has become: answers get worse and turns cost more as it grows, whatever the window, so
    a 400k context in a 1M window is long although it is under half full. The worse of the
    two wins.

    Attributes:
        warn_percent: The window fill, in percent, that warns.
        alert_percent: The window fill, in percent, that alerts.
        warn_tokens: The context size that warns; ``0`` turns the size rule's warning off.
        alert_tokens: The context size that alerts; ``0`` turns the size rule's alert off.
    """

    warn_percent: int = 70
    alert_percent: int = 90
    warn_tokens: int = 200_000
    alert_tokens: int = 400_000

    def level(self, status: ClientStatus) -> ContextLevel:
        """How worrying ``status``'s context is; ``OK`` when the client reported no fill."""
        percent = status.context_pct
        if percent is None and status.context_tokens is not None and status.context_window_size:
            percent = round(100 * status.context_tokens / status.context_window_size)
        tokens = status.context_tokens
        if _reached(percent, self.alert_percent) or _reached(tokens, self.alert_tokens):
            return ContextLevel.ALERT
        if _reached(percent, self.warn_percent) or _reached(tokens, self.warn_tokens):
            return ContextLevel.WARN
        return ContextLevel.OK


def _reached(value: int | None, threshold: int) -> bool:
    return value is not None and threshold > 0 and value >= threshold
