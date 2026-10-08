# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Who in a session made a turn: the main conversation, or an agent it started."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TurnRole(StrEnum):
    """Which side of a session a turn came from.

    Attributes:
        MAIN: The conversation the user talks to, and its own side calls (titles).
        AGENT: An agent (a subagent) the main conversation started, and its side calls.
    """

    MAIN = "main"
    AGENT = "agent"


@dataclass(frozen=True)
class TurnOrigin:
    """Where a turn came from, as read off its request.

    Attributes:
        role: The main conversation or an agent.
        agent: The agent's name when the client gives one, else ``None``; always
            ``None`` for the main conversation.
    """

    role: TurnRole = TurnRole.MAIN
    agent: str | None = None


MAIN = TurnOrigin()
