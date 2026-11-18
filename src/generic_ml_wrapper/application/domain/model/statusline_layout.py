# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Which blocks the status line shows, in which order, and where the agents' share shows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

#: The live line's blocks, in their default order. ``quota`` is the client's own allowance
#: block (Claude's rate-limit quota, Cursor's plan pools).
LINE_BLOCKS = ("model", "context", "quota", "cost", "git", "folder")
#: The session/job rows' fields, in their default order.
ROW_FIELDS = ("cost", "turns", "input", "output", "cache_read", "cache_write", "tools")
#: The row fields that can carry the agents' share after their value.
AGENT_FIELDS = ("turns", "input", "output", "cache_read", "cache_write")
#: The row fields that are token counts, by kind.
TOKEN_FIELDS = ("input", "output", "cache_read", "cache_write")


@dataclass(frozen=True)
class StatuslineLayout:
    """The status line's shown blocks in order, and the fields that show the agents' share.

    ``line`` and ``rows`` list what is shown, in the order shown; a block that is not
    listed is hidden. ``agents`` names the row fields followed by the agents' share. The
    defaults are the full line.
    """

    line: tuple[str, ...] = LINE_BLOCKS
    rows: tuple[str, ...] = ROW_FIELDS
    agents: frozenset[str] = frozenset(AGENT_FIELDS)

    @classmethod
    def of(
        cls,
        line: Iterable[str] | None = None,
        rows: Iterable[str] | None = None,
        agents: Iterable[str] | None = None,
    ) -> StatuslineLayout:
        """A layout from configured names, keeping only known ones, each once.

        ``None`` for any part means it was not configured, and takes its default. An
        unknown name is dropped rather than refused, so a typo hides nothing else.
        """
        return cls(
            LINE_BLOCKS if line is None else _known(line, LINE_BLOCKS),
            ROW_FIELDS if rows is None else _known(rows, ROW_FIELDS),
            frozenset(AGENT_FIELDS if agents is None else _known(agents, AGENT_FIELDS)),
        )


def _known(names: Iterable[str], allowed: tuple[str, ...]) -> tuple[str, ...]:
    """``names`` in their order, without unknown names or repeats."""
    return tuple(dict.fromkeys(name for name in names if name in allowed))
