# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``PreFlightRunnerPort`` that runs the script with gmlw's own Python."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.pre_flight_runner import PreFlightRunnerPort

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


class SubprocessPreFlightRunner(PreFlightRunnerPort):
    """Run the script with the interpreter gmlw runs on, so no other Python is needed.

    Its input is closed, so a script that waits for an answer fails instead of hanging the
    start; its output goes to the user's terminal.
    """

    def run(self, script: Path, cwd: str | None, env: Mapping[str, str]) -> int:
        """Run ``script`` and return its exit code.

        Args:
            script: The script, inside the attachment's stored folder.
            cwd: The folder the session launches in, or ``None`` for the current one.
            env: Variables added to the user's environment for the script.

        Returns:
            The script's exit code, or ``1`` if it could not be started.
        """
        try:
            completed = subprocess.run(  # noqa: S603  (gmlw's interpreter and a stored script, no shell)
                [sys.executable, str(script)],
                check=False,
                cwd=cwd,
                env={**os.environ, **env},
                stdin=subprocess.DEVNULL,
            )
        except OSError:
            return 1
        return completed.returncode
