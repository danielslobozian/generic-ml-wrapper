# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The banner shown atop ``gmlw --help``."""

from __future__ import annotations

import sys

from generic_ml_wrapper.application.wiring import localization as i18n

# The product name is not translated; the two lines of prose around it are, and are
# resolved per call rather than at import so they follow the active localiser.
_TITLE = "gmlw"

_BOLD_CYAN = "\033[1;36m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def banner() -> str:
    """Render the help banner, colored only when stdout is a terminal.

    Returns:
        The two-line banner (title + subtitle), no trailing newline.
    """
    tagline = i18n.t("cli.banner.tagline")
    subtitle_text = i18n.t("cli.banner.subtitle")
    if sys.stdout.isatty():
        title = f"{_BOLD_CYAN}{_TITLE}{_RESET} {_DIM}· {tagline}{_RESET}"
        subtitle = f"{_DIM}{subtitle_text}{_RESET}"
    else:
        title = f"{_TITLE} · {tagline}"
        subtitle = subtitle_text
    return f"{title}\n{subtitle}"
