# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""What the agents cost some turns: their own, and the main turns they caused."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts
from generic_ml_wrapper.application.domain.model.turn_origin import TurnRole

if TYPE_CHECKING:
    from collections.abc import Sequence

    from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage


@dataclass(frozen=True)
class AgentUsage:
    """The agents' part of some turns, in two halves that do not overlap.

    An agent's own turns are the first half. The second is the main conversation's turns
    made only because an agent was started or reported back: each re-reads the whole
    main context, so a long session that starts many agents pays for them twice.

    Attributes:
        turns: How many turns the agents made.
        tokens: The tokens of those turns, by kind.
        caused_turns: How many main-conversation turns the agents caused.
        caused_tokens: The tokens of those turns, by kind.
    """

    turns: int = 0
    tokens: TokenCounts = field(default_factory=TokenCounts)
    caused_turns: int = 0
    caused_tokens: TokenCounts = field(default_factory=TokenCounts)

    @classmethod
    def of(cls, turns: Sequence[TurnUsage]) -> AgentUsage | None:
        """The agents' part of ``turns``, or ``None`` when they had none."""
        own = [turn for turn in turns if turn.role is TurnRole.AGENT]
        caused = [turn for turn in turns if turn.role is TurnRole.MAIN and turn.caused_by_agent]
        if not own and not caused:
            return None
        return cls(len(own), TokenCounts.of(own), len(caused), TokenCounts.of(caused))
