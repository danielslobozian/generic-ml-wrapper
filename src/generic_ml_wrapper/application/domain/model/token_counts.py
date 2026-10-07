# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The four kinds of token a metered turn is billed for, kept apart."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage


@dataclass(frozen=True)
class TokenCounts:
    """Tokens summed over some turns, by kind.

    The four do not overlap (Anthropic's ``input_tokens`` counts only the prompt tokens
    neither read from nor written to the cache), so together they are the whole traffic.
    They are kept apart because they mean different things: a large cache read is the
    cache working, while a large cache write turn after turn is the cache being rebuilt.

    Attributes:
        input: Fresh prompt tokens.
        output: Completion tokens.
        cache_read: Prompt tokens served from the cache.
        cache_write: Prompt tokens written to the cache.
    """

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

    @classmethod
    def of(cls, turns: Iterable[TurnUsage]) -> TokenCounts:
        """Sum each kind over ``turns``."""
        counts = cls()
        for turn in turns:
            counts = cls(
                counts.input + turn.input_tokens,
                counts.output + turn.output_tokens,
                counts.cache_read + turn.cache_read_tokens,
                counts.cache_write + turn.cache_creation_tokens,
            )
        return counts
