# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``CursorCliCaller``: launch cursor-agent and install its status line (no metering)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.caller import context_file, status_line_config
from generic_ml_wrapper.adapter.outbound.caller.context_opening import read_first_opening
from generic_ml_wrapper.adapter.outbound.caller.status_line_config import StatusLineSnapshot
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller

BINARY = "cursor-agent"
_CONFIG = Path.home() / ".cursor" / "cli-config.json"
_STATUSLINE: dict[str, object] = {
    "type": "command",
    "command": "gmlw statusline",
    "updateIntervalMs": 2000,
    "timeoutMs": 5000,
}


class CursorCliCaller(CliCaller):
    """Launch cursor-agent for a run, with the wrapper's status line, without metering.

    cursor-agent hosts a command-backed status line (``~/.cursor/cli-config.json``),
    so ``start_metering`` points it at ``gmlw statusline`` and ``end_metering``
    restores the prior setting. Its ``--resume <name>`` both creates and resumes a
    session. It has no system-prompt flag, so injected context is written to a file
    the agent is told to read first. This light client does not meter usage.
    """

    def __init__(self, run: RunContext) -> None:
        """Bind the caller to a run.

        Args:
            run: The run this caller will launch.
        """
        super().__init__(run)
        self._snapshot: StatusLineSnapshot | None = None

    def can_deliver_statusline(self) -> bool:
        """cursor-agent hosts a command-backed status line the wrapper renders into."""
        return True

    def start_metering(self) -> None:
        """Point cursor-agent's status line at ``gmlw statusline`` for this session."""
        if self.can_deliver_statusline():
            self._snapshot = status_line_config.install(_CONFIG, _STATUSLINE)

    def end_metering(self) -> None:
        """Restore cursor-agent's previous status-line setting."""
        if self._snapshot is not None:
            status_line_config.restore(_CONFIG, self._snapshot)

    def command(self, opening: str | None = None) -> list[str]:
        """Build the ``cursor-agent`` command line for this run.

        Args:
            opening: The opening message to start the session on, or ``None``.

        Returns:
            The argv list to execute.
        """
        argv = [BINARY, "--resume", self.run.session_id]
        if opening is not None:
            argv.append(opening)
        return argv

    def start_client(self) -> int:
        """Launch cursor-agent, blocking until it exits.

        Injected context (new sessions only) is written to a temporary file the
        agent is told to read first, removed when the client exits.

        Returns:
            The client's exit code.
        """
        if self.run.context is not None and not self.run.resume:
            path = context_file.write(self.run.job, self.run.session_id, self.run.context)
            return self._run(self.command(read_first_opening(str(path), self.run.kickoff)))
        return self._run(self.command(self.run.kickoff))

    def _run(self, argv: list[str]) -> int:
        env = {
            **os.environ,
            **dict(self.run.env),
            "GMLW_JOB": self.run.job,
            "GMLW_SESSION": self.run.session_id,
            "GMLW_CLIENT": self.run.client,
        }
        # Trusted argv from our resolved run; no shell. The program is PATH-resolved (BINARY).
        completed = subprocess.run(argv, check=False, cwd=self.run.cwd, env=env)  # noqa: S603
        return completed.returncode
