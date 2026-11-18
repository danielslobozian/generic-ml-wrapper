# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ExecutionTags value object: the key/value pairs a turn was tagged with."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class ExecutionTags:
    """The tags a turn ran under, from the conversation's latest ``gmlw-execution`` object.

    The user decides the keys -- one, two or ten of them -- and gmlw never requires any.
    Each key/value pair is a tag of its own, so a report can total by one key or narrow
    to one pair.

    Attributes:
        pairs: ``(key, value)`` pairs, by key; values are text.
    """

    pairs: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_mapping(cls, tags: Mapping[str, str]) -> ExecutionTags:
        """The tags in ``tags``, ordered by key."""
        return cls(tuple(sorted(tags.items())))

    def as_dict(self) -> dict[str, str]:
        """The tags as ``{key: value}``, by key."""
        return dict(self.pairs)

    def get(self, key: str) -> str | None:
        """The value of ``key``, or ``None`` when the turn has no such tag."""
        return dict(self.pairs).get(key)

    def has(self, key: str, value: str) -> bool:
        """Whether the turn carries the pair ``key=value``."""
        return (key, value) in self.pairs
