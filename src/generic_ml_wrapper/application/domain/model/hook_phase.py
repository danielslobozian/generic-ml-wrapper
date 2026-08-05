# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The HookPhase: the lifecycle seam a hook runs at."""

from __future__ import annotations

from enum import StrEnum


class HookPhase(StrEnum):
    """The lifecycle seam a hook runs at, doubling as its config value.

    A ``str`` enum so a phase is written verbatim in ``[[hooks]]`` (``phase = "..."``).
    """

    PRE_LAUNCH = "pre-launch"  # after context compiled + caller resolved, before launch
    POST_SESSION = "post-session"  # after the client exits
