# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``InterruptScopePort`` over operating-system signals.

Only the interrupt is taken. A kill or a hang-up is deliberately left alone: the caller
adapter forwards those to the client it launched, so the run ends by returning through the
launch sequence rather than by unwinding through it -- which is what lets teardown happen.
"""

from __future__ import annotations

import signal
from contextlib import contextmanager
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.interrupt_scope import InterruptScopePort

if TYPE_CHECKING:
    from collections.abc import Generator


def _ignore(_signum: int, _frame: object) -> None:
    """Absorb the interrupt: the client is handling it."""


class SignalInterruptScope(InterruptScopePort):
    """Hand the interrupt to the client by ignoring it here, and restore it afterwards."""

    @contextmanager
    def client_owns_interrupts(self) -> Generator[None]:
        """Ignore the interrupt for the block, restoring the previous handler after."""
        previous = signal.signal(signal.SIGINT, _ignore)
        try:
            yield
        finally:
            signal.signal(signal.SIGINT, previous)
