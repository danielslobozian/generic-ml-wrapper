# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for running an install/update command on the user's behalf."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CommandRunnerPort(ABC):
    """Run a shell command the user has chosen to let gmlw execute (e.g. an installer)."""

    @abstractmethod
    def run(self, command: str) -> int:
        """Run ``command`` in a shell, streaming its output, and return the exit code.

        Args:
            command: The command line to run (a trusted catalog install/update string).

        Returns:
            The process exit code (``0`` on success), or a non-zero code on failure.
        """
