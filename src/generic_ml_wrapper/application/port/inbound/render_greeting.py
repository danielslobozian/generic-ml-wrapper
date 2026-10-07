# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the free host greeting shown at launch."""

from __future__ import annotations

from abc import ABC, abstractmethod


class RenderGreeting(ABC):
    """Compose the wrapper's free, local host greeting for the selected persona."""

    @abstractmethod
    def execute(self) -> str | None:
        """Return the greeting to show at launch, or ``None`` when there is none.

        Returns:
            The rendered greeting, or ``None`` when the companion is off (no persona
            selected) or the selected persona has no greeting.
        """
