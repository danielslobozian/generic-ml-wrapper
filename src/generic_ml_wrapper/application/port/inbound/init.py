# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the forced first-run init: the ordered setup interview."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class InitOutcome:
    """What the init interview resolved, for the caller to narrate.

    Attributes:
        language: The language gmlw will speak to the user.
        name: The name the companion will address the user by.
        role: The default role chosen (the functional hat).
        environment: The default environment chosen (the place work happens).
        persona: The persona chosen, or ``None`` when the companion was left off.
        client: The default client chosen, or ``None`` when none was installed/picked.
        found: The installed clients detected, in canonical order (empty when none).
        fresh: ``True`` when this was a brand-new install (full config seeded);
            ``False`` on a legacy install (only the gate marker was appended).
    """

    language: str
    name: str
    role: str
    environment: str
    persona: str | None
    client: str | None
    found: list[str]
    fresh: bool


class Init(ABC):
    """Run the forced first-run setup: language → name → role → environment → persona → client."""

    @abstractmethod
    def execute(self) -> InitOutcome:
        """Run the ordered interview, persist the result, and report what it decided.

        Returns:
            The outcome of the interview.
        """
