# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The launch arguments a client is started with, parsed from one configured string.

The string is opaque to gmlw: whatever the user wrote is handed to their client
verbatim. Only the splitting is ours, and it has one platform wrinkle worth naming
(see :meth:`ClientArguments.parse`).

An unbalanced quote is the user's typo, and it must not take down the launch — but it
must not pass unmentioned either: dropping the arguments silently would start the client
without the flags the user asked for and look like success. So a failed parse is carried
on the value itself, as :attr:`unparseable`, for the caller to report. The domain does
not speak to the user, and does not decide what a diagnostic looks like.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass


@dataclass(frozen=True)
class ClientArguments:
    """Launch tokens, plus the reason the text yielded none when it should have.

    Attributes:
        tokens: The parsed launch tokens; empty when the text was blank or unparseable.
        unparseable: The parser's complaint when the text could not be split, else ``""``.
            Empty text is not a failure and leaves this empty.
    """

    tokens: tuple[str, ...] = ()
    unparseable: str = ""

    @classmethod
    def parse(cls, text: str, *, posix: bool) -> ClientArguments:
        r"""Split an argument string into launch tokens.

        Args:
            text: The raw argument string, as configured or typed.
            posix: Whether to split by POSIX rules. Passed in rather than read from the
                process: which operating system this is running on is not something the
                domain may ask. POSIX splitting treats a backslash as an escape, so a
                Windows path (``--add-dir C:\\work``) would arrive with its separators
                eaten; Windows keeps the quotes inside the tokens instead, which is what
                the process launcher re-quotes correctly there anyway.

        Returns:
            The parsed arguments; empty tokens when the string is blank, and empty
            tokens with a filled ``unparseable`` when it could not be split.
        """
        if not text or not text.strip():
            return cls()
        try:
            return cls(tuple(shlex.split(text, posix=posix)))
        except ValueError as error:
            return cls(unparseable=str(error))
