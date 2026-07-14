# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``ClaudeCliCaller``: launch Claude Code, install the status line, meter the run."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.caller import context_file, status_line_config
from generic_ml_wrapper.adapter.outbound.caller.status_line_config import StatusLineSnapshot
from generic_ml_wrapper.adapter.outbound.gateway.relay import MeteringRelay
from generic_ml_wrapper.application.domain.model.run import RunContext
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller
from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
    from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
    from generic_ml_wrapper.application.port.outbound.transcript import TranscriptPort

BINARY = "claude"
_SETTINGS = Path.home() / ".claude" / "settings.json"
_STATUSLINE: dict[str, object] = {"type": "command", "command": "gmlw statusline", "padding": 0}


class ClaudeCliCaller(CliCaller):
    """Launch Claude Code for a run, metered via the status line and a local relay.

    ``start_metering`` points Claude Code's ``statusLine`` at ``gmlw statusline`` and
    stands up a :class:`MeteringRelay`, pointing Claude at it via ``ANTHROPIC_BASE_URL``
    to record per-turn tokens; ``end_metering`` tears both down. If the relay cannot
    start, the launch falls back to unmetered (status line only). A new session may
    carry injected ``context`` (Claude's system prompt), an opening ``kickoff``, and a
    ``cwd``; the run's identity is exported as ``GMLW_JOB`` / ``GMLW_SESSION`` /
    ``GMLW_CLIENT``.
    """

    def __init__(
        self,
        run: RunContext,
        metering: PerTurnMeteringPort,
        interceptors: InterceptorChain | None = None,
        transcript: TranscriptPort | None = None,
    ) -> None:
        """Bind the caller to a run, its metering store, and the interceptor chain.

        Args:
            run: The run this caller will launch and meter.
            metering: Where the relay records per-turn usage.
            interceptors: The interceptor chain the relay applies to wire traffic.
            transcript: Where the relay records each call's transcript, or ``None``.
        """
        super().__init__(run)
        self._metering = metering
        self._interceptors = interceptors
        self._transcript = transcript
        self._snapshot: StatusLineSnapshot | None = None
        self._relay: MeteringRelay | None = None

    def can_deliver_statusline(self) -> bool:
        """Claude Code hosts a command-backed status line the wrapper renders into."""
        return True

    def can_meter_per_call(self) -> bool:
        """This caller records per-turn usage via its metering relay."""
        return True

    def start_metering(self) -> None:
        """Install the status line and start the metering relay for this session."""
        if self.can_deliver_statusline():
            self._snapshot = status_line_config.install(_SETTINGS, _STATUSLINE)
        relay = MeteringRelay(
            job=self.run.job,
            session=self.run.session_id,
            metering=self._metering,
            client=self.run.client,
            transcript=self._transcript,
            interceptors=self._interceptors,
        )
        try:
            relay.start()
        except OSError as error:
            log.warning(f"metering relay failed to start ({error}); launching unmetered")
            return
        self._relay = relay

    def end_metering(self) -> None:
        """Stop the metering relay and restore the status line."""
        if self._relay is not None:
            self._relay.stop()
            self._relay = None
        if self._snapshot is not None:
            status_line_config.restore(_SETTINGS, self._snapshot)

    def command(self, context_file: str | None = None) -> list[str]:
        """Build the ``claude`` command line for this run.

        Args:
            context_file: A file whose contents to append to the system prompt, or
                ``None`` (only used for a new session).

        Returns:
            The argv list to execute.
        """
        run = self.run
        if run.resume:
            argv = [BINARY, "--resume", run.uuid or run.session_id]
        else:
            argv = [BINARY, "-n", run.session_id]
            if run.uuid is not None:
                argv += ["--session-id", run.uuid]
            if context_file is not None:
                argv += ["--append-system-prompt-file", context_file]
        if run.kickoff is not None:
            argv.append(run.kickoff)
        return argv

    def start_client(self) -> int:
        """Launch Claude, blocking until it exits.

        Injected context (new sessions only) is persisted per session and passed via
        ``--append-system-prompt-file`` -- a durable provenance artifact.

        Returns:
            The client's exit code.
        """
        if self.run.context is not None and not self.run.resume:
            path = context_file.write(self.run.job, self.run.session_id, self.run.context)
            return self._run(self.command(str(path)))
        return self._run(self.command())

    def _extra_env(self) -> dict[str, str]:
        """Point Claude at the relay when it is running.

        Returns:
            ``ANTHROPIC_BASE_URL`` for the relay, or empty when it isn't running.
        """
        return {} if self._relay is None else {"ANTHROPIC_BASE_URL": self._relay.base_url}

    def _run(self, argv: list[str]) -> int:
        env = {
            **os.environ,
            **dict(self.run.env),
            **self._extra_env(),
            "GMLW_JOB": self.run.job,
            "GMLW_SESSION": self.run.session_id,
            "GMLW_CLIENT": self.run.client,
        }
        # Trusted argv from our resolved run; no shell. The program is PATH-resolved (BINARY).
        completed = subprocess.run(argv, check=False, cwd=self.run.cwd, env=env)  # noqa: S603
        return completed.returncode
