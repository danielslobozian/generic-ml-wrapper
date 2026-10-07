# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``CommandRunnerPort`` that runs a command in a shell, inheriting the terminal."""

from __future__ import annotations

import subprocess

from generic_ml_wrapper.application.port.outbound.command_runner import CommandRunnerPort


class SubprocessCommandRunner(CommandRunnerPort):
    """Run an install/update command via the shell, streaming it to the user's terminal.

    The commands are the vendor install one-liners from the trusted client catalog
    (``curl … | bash``, ``uv tool install …``), which are shell pipelines — so this
    runs them through the shell rather than as an argv list. It is only ever handed a
    catalog string, and only after the user explicitly chose "run it for me".
    """

    def run(self, command: str) -> int:
        """Run ``command`` in a shell and return its exit code.

        Args:
            command: The trusted catalog install/update command line.

        Returns:
            The process exit code, or ``1`` if the shell could not be started.
        """
        try:
            return subprocess.run(command, shell=True, check=False).returncode  # noqa: S602
        except OSError:
            return 1
