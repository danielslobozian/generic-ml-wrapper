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

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
        MessageSourceAccessor,
    )


class TtyTextPrompt:
    """Ask one free-text question at an interactive terminal; else return the default."""

    def __init__(self, message_source: MessageSourceAccessor) -> None:
        """Bind the prompt to a message source for its fixed ``[default …]`` fragment.

        Args:
            message_source: The message source supplying the ``prompt.ask_text`` fragment.
        """
        self._message_source = message_source

    def ask(
        self, header: str, default: str, message_source: MessageSourceAccessor | None = None
    ) -> str:
        """Ask ``header`` and return the typed answer, or ``default``.

        Writes to ``sys.stderr`` and reads from ``sys.stdin`` (both resolved at call
        time), so a non-TTY run resolves to ``default`` rather than blocking.

        Args:
            header: The already-localised question line printed above the prompt.
            default: The value used on an empty line, at end of input, or off a terminal.
            message_source: The message source for the ``[default …]`` fragment; ``None`` uses the
                construction-time one.

        Returns:
            The trimmed answer, or ``default`` when nothing usable was typed.
        """
        if not (sys.stdin.isatty() and sys.stderr.isatty()):
            return default
        message_source = message_source or self._message_source
        print(header, file=sys.stderr)
        print(
            message_source.get_message("prompt.ask_text", default=default),
            end="",
            file=sys.stderr,
            flush=True,
        )
        line = sys.stdin.readline()
        if line == "":  # end of input
            return default
        return line.strip() or default
