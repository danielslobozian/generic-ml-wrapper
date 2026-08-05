# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``CursorCliCallerAdapter``: launch cursor-agent and install its status line (no metering)."""

from __future__ import annotations

import os
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.caller import context_file, status_line_config
from generic_ml_wrapper.adapter.outbound.caller.child_process import ChildProcess
from generic_ml_wrapper.adapter.outbound.caller.context_opening import read_first_opening
from generic_ml_wrapper.adapter.outbound.caller.status_line_config import StatusLineSnapshot
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCallerPort

BINARY = "cursor-agent"
_CONFIG = Path.home() / ".cursor" / "cli-config.json"
_STATUSLINE: dict[str, object] = {
    "type": "command",
    "command": status_line_config.statusline_command(),
    "updateIntervalMs": 2000,
    "timeoutMs": 5000,
}


class CursorCliCallerAdapter(CliCallerPort):
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
            self._snapshot = status_line_config.install_best_effort(_CONFIG, _STATUSLINE)

    def end_metering(self) -> None:
        """Restore cursor-agent's previous status-line setting."""
        if self._snapshot is not None:
            status_line_config.restore(_CONFIG, self._snapshot)

    def can_resume(self) -> bool:
        """cursor-agent reopens a chat by the session id we name it with."""
        return True

    def command(self, opening: str | None = None) -> list[str]:
        """Build the ``cursor-agent`` command line for this run.

        Args:
            opening: The opening message to start the session on, or ``None``.

        Returns:
            The argv list to execute.
        """
        argv = [BINARY, "--resume", self.run.session_id, *self.run.client_args]
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
        return ChildProcess().run(argv, self.run.cwd, env)
