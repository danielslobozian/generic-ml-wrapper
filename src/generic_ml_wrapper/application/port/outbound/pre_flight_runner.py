# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for running an attachment's pre-flight script."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


class PreFlightRunnerPort(ABC):
    """Run an attachment's pre-flight script and wait for it to exit."""

    @abstractmethod
    def run(self, script: Path, cwd: str | None, env: Mapping[str, str]) -> int:
        """Run ``script`` with Python, without input, and return its exit code.

        Whatever the script starts in the background is its own: the runner waits only
        for the script itself.

        Args:
            script: The script, inside the attachment's stored folder.
            cwd: The folder the session launches in, or ``None`` for the current one.
            env: Variables added to the user's environment for the script.

        Returns:
            The script's exit code, or a non-zero code when it could not be started.
        """
