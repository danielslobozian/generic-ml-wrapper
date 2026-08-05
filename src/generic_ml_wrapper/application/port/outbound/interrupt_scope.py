# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for handing interrupt ownership to the client for a session."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager


class InterruptScopePort(ABC):
    """Let the launched client own the interrupt while it holds the terminal.

    The wrapper supervises a session; it does not run it. When the user interrupts, the
    interrupt is meant for the client, which has its own idea of what to abandon. If the
    wrapper took it instead it would unwind past its own teardown, leaving the metering
    relay running and the client's settings still pointing at a status line that has gone.

    Restoring on the way out is part of the contract: the wrapper owns interrupts again
    the moment the session ends, however it ends.
    """

    @abstractmethod
    def client_owns_interrupts(self) -> AbstractContextManager[None]:
        """Give the client the interrupt for the duration of the block.

        Returns:
            A context manager that restores the previous arrangement on exit.
        """
