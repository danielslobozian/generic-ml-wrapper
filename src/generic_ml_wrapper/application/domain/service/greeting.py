# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Pure composition of the free host greeting from live facts."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.workspace import Workspace

_MORNING_START = 5
_AFTERNOON_START = 12
_EVENING_START = 18
_SPACES = re.compile(r" {2,}")


def daypart(hour: int) -> str:
    """Return the time-of-day greeting word for an hour (0-23).

    Grounded in the real local hour, so a late-night session is never greeted with
    "Good morning". Night (before 5am, from 6pm on) reads as evening.

    Args:
        hour: The local hour, 0-23.

    Returns:
        ``"Good morning"``, ``"Good afternoon"``, or ``"Good evening"``.
    """
    if _MORNING_START <= hour < _AFTERNOON_START:
        return "Good morning"
    if _AFTERNOON_START <= hour < _EVENING_START:
        return "Good afternoon"
    return "Good evening"


def repo_note(workspace: Workspace) -> str:
    """Return a leading-space clause naming the repo (and branch), or ``""``.

    Args:
        workspace: The inspected working environment.

    Returns:
        ``" You're in <repo> (<branch>)."`` inside a git repo, else ``""`` — the
        leading space lets it slot into a template with nothing to trim when absent.
    """
    if workspace.repo is None:
        return ""
    where = f"{workspace.repo} ({workspace.branch})" if workspace.branch else workspace.repo
    return f" You're in {where}."


def render_greeting(template: str, *, name: str, daypart: str, repo_note: str) -> str:
    """Fill a persona's greeting template from live facts.

    Args:
        template: The persona's greeting, with ``{name}``/``{daypart}``/
            ``{repo_note}`` slots.
        name: The user's name.
        daypart: The time-of-day word (see :func:`daypart`).
        repo_note: The repository clause (see :func:`repo_note`).

    Returns:
        The rendered, single-line greeting (collapsed spaces, trimmed).
    """
    text = (
        template.replace("{name}", name)
        .replace("{daypart}", daypart)
        .replace("{repo_note}", repo_note)
    )
    return _SPACES.sub(" ", text).strip()


def greeting_context(greeting: str) -> str:
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
