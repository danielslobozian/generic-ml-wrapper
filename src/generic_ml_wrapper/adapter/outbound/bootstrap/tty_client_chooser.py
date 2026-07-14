# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``ClientChooserPort`` that prompts on a terminal, declining when there is none."""

from __future__ import annotations

import sys

from generic_ml_wrapper.application.port.outbound.client_chooser import ClientChooserPort


class TtyClientChooser(ClientChooserPort):
    """Ask the user to pick a default client, but only at an interactive terminal.

    The prompt is written to stderr (stdout stays clean for ``--json`` and view
    output), and it reads from stdin. When either end is not a TTY the chooser
    declines (returns ``None``) so a piped or automated run never blocks.
    """

    def choose(self, candidates: list[str]) -> str | None:
        """Prompt for a default client, defaulting to the first on an empty line.

        Args:
            candidates: The installed clients to choose among (two or more).

        Returns:
            The chosen client, or ``None`` when there is no terminal to prompt on.
        """
        if not (sys.stdin.isatty() and sys.stderr.isatty()):
            return None
        print("gmlw: first run — which client should I wrap by default?", file=sys.stderr)
        for index, name in enumerate(candidates, start=1):
            print(f"  {index}) {name}", file=sys.stderr)
        while True:
            reply = self._read(f"Pick a number [1-{len(candidates)}, default 1]: ")
            if reply is None:
                return None
            reply = reply.strip()
            if not reply:
                return candidates[0]
            if reply.isdigit() and 1 <= int(reply) <= len(candidates):
                return candidates[int(reply) - 1]
            print(f"  '{reply}' is not one of 1-{len(candidates)}.", file=sys.stderr)

    def _read(self, prompt: str) -> str | None:
        """Read one line for the prompt, or ``None`` at end of input."""
        print(prompt, end="", file=sys.stderr, flush=True)
        line = sys.stdin.readline()
        return None if line == "" else line
