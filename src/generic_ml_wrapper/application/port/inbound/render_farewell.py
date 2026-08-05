# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the parting line shown once a client has exited."""

from __future__ import annotations

from abc import ABC, abstractmethod


class RenderFarewellUseCase(ABC):
    """Render the goodbye, when there is a companion to say it."""

    @abstractmethod
    def execute(self) -> str | None:
        """Return the parting line, or ``None`` when the companion is off.

        Both decisions are the application's: whether a companion is configured at all,
        and what to call the user when they have not said. A caller that resolved the
        name itself would have to know the fallback, which is a rule about the product.

        Returns:
            The line to show, or ``None``.
        """
