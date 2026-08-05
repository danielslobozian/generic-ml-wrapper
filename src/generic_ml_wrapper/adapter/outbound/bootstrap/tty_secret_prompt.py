# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``SecretPromptPort`` over the terminal, degrading to a piped line.

At a terminal the value is read without echo, so it does not appear on screen and cannot
be recovered by scrolling back. Off a terminal there is nobody to hide it from and nothing
to prompt: the value is one line on standard input, which is what a script would send.
"""

from __future__ import annotations

import getpass
import sys

from generic_ml_wrapper.application.port.outbound.secret_prompt import SecretPromptPort


class TtySecretPromptAdapter(SecretPromptPort):
    """Read a secret from the terminal without echoing it, or from a pipe."""

    def ask_secret(self, label: str) -> str:
        """Read one secret value, prompting only when somebody is there to read it."""
        if sys.stdin.isatty():
            return getpass.getpass(f"{label}: ")
        return sys.stdin.readline().rstrip("\n")
