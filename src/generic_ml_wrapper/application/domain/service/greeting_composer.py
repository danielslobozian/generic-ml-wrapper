# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Pure composition of the free host greeting from live facts."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_MORNING_START = 5
_AFTERNOON_START = 12
_EVENING_START = 18
_SPACES = re.compile(r" {2,}")


class GreetingComposer:
    """Composes the free host greeting from live facts: the hour, the repo, the persona."""

    def greeting_context(self, greeting: str) -> str:
        """Wrap a rendered greeting as a launch-context instruction the client renders in-band.

        The host greeting used to print to stderr, which the client clears the moment it takes
        the screen — structurally invisible. Delivered as context instead, the client renders it
        in-band at the top of the session. Model-directed framing, kept in English to match the
        workflow kickoff (the other model-directed launch text).

        Args:
            greeting: The rendered greeting line.

        Returns:
            A markdown context section carrying the greeting.
        """
        return (
            "# Greeting\n"
            "Open this session by greeting the user in your companion voice, then continue:\n\n"
            f"{greeting}"
        )
