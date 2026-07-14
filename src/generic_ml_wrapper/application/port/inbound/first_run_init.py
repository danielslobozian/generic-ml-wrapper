# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for first-run initialization (client detection + config seed)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class FirstRunOutcome:
    """What first-run init decided, for the caller to narrate.

    Attributes:
        found: The installed clients detected, in canonical order (empty when none).
        chosen: The client seeded as the default, or ``None`` when none was chosen
            (nothing installed, or a non-interactive multi-client run).
    """

    found: list[str]
    chosen: str | None


class FirstRunInit(ABC):
    """Detect installed clients, pick a default, and seed the runtime layout."""

    @abstractmethod
    def execute(self) -> FirstRunOutcome:
        """Run first-run init and report what it decided.

        Returns:
            The outcome: the clients found and the default chosen (if any).
        """
