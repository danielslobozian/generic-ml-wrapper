# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""How many times a model called each tool: ``Bash`` three times, ``WebSearch`` once."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@dataclass(frozen=True)
class ToolCalls:
    """The calls a model made, counted by tool name.

    Only the name is kept -- never what a call asked or what it returned. Names are the
    client's own (``Bash``, ``exec``, ``web_search``), so the same kind of tool can read
    differently from one client to the next.

    Attributes:
        counts: ``(name, calls)`` pairs, most called first, then by name; no zero counts.
    """

    counts: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        """Reject a count below one: a tool that was not called is not listed."""
        for name, calls in self.counts:
            if calls < 1:
                message = f"{name} must have been called at least once, got {calls}"
                raise ValueError(message)

    @classmethod
    def of(cls, names: Iterable[str]) -> ToolCalls:
        """Count each name in ``names``, one call each."""
        return cls.from_counts(Counter(names))

    @classmethod
    def from_counts(cls, counts: Mapping[str, int]) -> ToolCalls:
        """The calls in ``counts`` (name to calls), ordered; zero counts dropped."""
        ordered = sorted(
            ((name, calls) for name, calls in counts.items() if calls > 0),
            key=lambda pair: (-pair[1], pair[0]),
        )
        return cls(tuple(ordered))

    @classmethod
    def summed(cls, many: Iterable[ToolCalls]) -> ToolCalls:
        """Every call in ``many``, added up per tool."""
        total: Counter[str] = Counter()
        for calls in many:
            total.update(dict(calls.counts))
        return cls.from_counts(total)

    @property
    def total(self) -> int:
        """How many calls, whatever the tool."""
        return sum(calls for _, calls in self.counts)

    def as_dict(self) -> dict[str, int]:
        """The counts as ``{name: calls}``, in the same order."""
        return dict(self.counts)
