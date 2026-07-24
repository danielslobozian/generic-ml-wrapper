# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The launch banner for the interactive menu.

The gmlw logo (figlet "small", the same font ``bmlw`` uses) framed in a rounded box,
with the supported clients on the left and the version on the right. Both the version and
the client list are *derived* -- from the package version and the client catalog -- so the
banner can never drift from what the tool actually is. No ANSI here: the Textual stylesheet
colours it.
"""

from __future__ import annotations

from generic_ml_wrapper import __version__
from generic_ml_wrapper.application.domain.model import client_catalog

# "generic ml wrapper" rendered in the figlet "small" font. Stored as escaped literals
# (from ``repr``) so the many backslashes need no raw-string handling.
_ART_LINES = [
    "                       _            _",
    " __ _ ___ _ _  ___ _ _(_)__   _ __ | | __ __ ___ _ __ _ _ __ _ __  ___ _ _",
    "/ _` / -_) ' \\/ -_) '_| / _| | '  \\| | \\ V  V / '_/ _` | '_ \\ '_ \\/ -_) '_|",
    "\\__, \\___|_||_\\___|_| |_\\__| |_|_|_|_|  \\_/\\_/|_| \\__,_| .__/ .__/\\___|_|",
    "|___/                                                  |_|  |_|",
]

_PAD = 2


def _clients_line() -> str:
    """The supported clients, joined for the banner's footer (e.g. ``claude · cursor``)."""
    return " · ".join(info.name for info in client_catalog.SUPPORTED)


def boxed_banner() -> str:
    """Render the logo in a rounded box with the clients (left) and version (right).

    Returns:
        The multi-line banner, ready to drop into a Textual ``Static`` (uncoloured).
    """
    left = _clients_line()
    right = f"v{__version__}"
    inner = max(*(len(line) for line in _ART_LINES), len(left) + len(right) + 1)
    width = inner + _PAD * 2
    out = ["╭" + "─" * width + "╮"]
    out += [f"│{' ' * _PAD}{line.ljust(inner)}{' ' * _PAD}│" for line in _ART_LINES]
    gap = max(inner - len(left) - len(right), 1)
    out.append(f"│{' ' * _PAD}{left}{' ' * gap}{right}{' ' * _PAD}│")
    out.append("╰" + "─" * width + "╯")
    return "\n".join(out)
