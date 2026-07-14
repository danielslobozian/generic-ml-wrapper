# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The banner shown atop ``gmlw --help``."""

from __future__ import annotations

import sys

_TITLE = "gmlw"
_TAGLINE = "a wrapper around an ML coding CLI"
_SUBTITLE = "enter at a job · one resumable, metered session · optional workflow"

_BOLD_CYAN = "\033[1;36m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def banner() -> str:
    """Render the help banner, colored only when stdout is a terminal.

    Returns:
        The two-line banner (title + subtitle), no trailing newline.
    """
    if sys.stdout.isatty():
        title = f"{_BOLD_CYAN}{_TITLE}{_RESET} {_DIM}· {_TAGLINE}{_RESET}"
        subtitle = f"{_DIM}{_SUBTITLE}{_RESET}"
    else:
        title = f"{_TITLE} · {_TAGLINE}"
        subtitle = _SUBTITLE
    return f"{title}\n{subtitle}"
