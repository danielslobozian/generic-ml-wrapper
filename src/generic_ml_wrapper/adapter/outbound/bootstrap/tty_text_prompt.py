# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``TextPromptPort`` for a single free-text answer, resolving to a default off a terminal.

The companion of :mod:`tty_prompt` for the free-text steps of first-run init (name, role,
environment): it writes the question to stderr and reads one line from stdin, so stdout
stays clean, and it falls back to the supplied default whenever either end is not a TTY —
a forced pass must always resolve a value and never block.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.text_prompt import TextPromptPort

if TYPE_CHECKING:
    from generic_ml_wrapper.common.i18n import Localizer


class TtyTextPrompt(TextPromptPort):
    """Ask one free-text question at an interactive terminal; else return the default."""

    def __init__(self, i18n: Localizer) -> None:
        """Bind the prompt to a localiser for its fixed ``[default …]`` fragment.

        Args:
            i18n: The localiser supplying the ``prompt.ask_text`` fragment.
        """
        self._i18n = i18n

    def ask(self, header: str, default: str, i18n: Localizer | None = None) -> str:
        """Ask ``header`` and return the typed answer, or ``default``.

        Writes to ``sys.stderr`` and reads from ``sys.stdin`` (both resolved at call
        time), so a non-TTY run resolves to ``default`` rather than blocking.

        Args:
            header: The already-localised question line printed above the prompt.
            default: The value used on an empty line, at end of input, or off a terminal.
            i18n: The localiser for the ``[default …]`` fragment; ``None`` uses the
                construction-time one.

        Returns:
            The trimmed answer, or ``default`` when nothing usable was typed.
        """
        if not (sys.stdin.isatty() and sys.stderr.isatty()):
            return default
        loc = i18n or self._i18n
        print(header, file=sys.stderr)
        print(loc.t("prompt.ask_text", default=default), end="", file=sys.stderr, flush=True)
        line = sys.stdin.readline()
        if line == "":  # end of input
            return default
        return line.strip() or default
