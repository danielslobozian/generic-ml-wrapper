# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Vibe (Mistral CLI) callers: launch vibe, optionally through a per-turn relay."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.caller import context_file, vibe_config
from generic_ml_wrapper.adapter.outbound.caller.context_opening import read_first_opening
from generic_ml_wrapper.adapter.outbound.gateway import openai_chat
from generic_ml_wrapper.adapter.outbound.gateway.relay import MeteringRelay
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller
from generic_ml_wrapper.common import i18n
from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.run import RunContext
    from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
    from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
    from generic_ml_wrapper.application.port.outbound.transcript import TranscriptPort

BINARY = "vibe"
_VIBE_CONFIG = Path.home() / ".vibe" / "config.toml"


class VibeCliCaller(CliCaller):
    """Launch vibe (Mistral's CLI) for a run, routed through a per-turn metering relay.

    vibe mints its own UUID session id and exposes no way to set one at launch, so
    the wrapper cannot bind or resume a session by its own id — :meth:`can_resume`
    is ``False`` — and it has no status-line hook. It takes its operating context via
    a "read this file first" opening message (it has no system-prompt flag).
    ``start_metering`` stands up a relay pointed at the active model's upstream and
    writes a throwaway ``VIBE_HOME`` whose config repoints that provider at the relay;
    if the relay cannot start (or the config can't be read), vibe launches unmetered.
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
        self._relay: MeteringRelay | None = None
        self._vibe_home: str | None = None

    def can_resume(self) -> bool:
        """Vibe mints its own session id and cannot be told one at launch."""
        return False

    def can_meter_per_call(self) -> bool:
        """This caller records per-turn usage via its metering relay."""
        return True

    def start_metering(self) -> None:
        """Start the relay and write the throwaway VIBE_HOME pointed at it."""
        try:
            source_text = _VIBE_CONFIG.read_text(encoding="utf-8")
        except OSError as error:
            log.warning(i18n.t("log.vibe_config_unreadable", config=_VIBE_CONFIG, error=error))
            return
        upstream = vibe_config.active_upstream(source_text)
        if upstream is None:
            log.warning(i18n.t("log.vibe_no_upstream"))
            return
        relay = MeteringRelay(
            job=self.run.job,
            session=self.run.session_id,
            metering=self._metering,
            client=self.run.client,
            transcript=self._transcript,
            upstream_base=upstream,
            usage_reader=openai_chat.read_usage,
            is_metered=_vibe_metered,
            interceptors=self._interceptors,
        )
        try:
            relay.start()
        except OSError as error:
            log.warning(i18n.t("log.vibe_relay_failed", error=error))
            return
        self._relay = relay
        home = Path(tempfile.mkdtemp(prefix="gmlw-vibe-"))
        (home / "config.toml").write_text(
            vibe_config.redirect(source_text, upstream, relay.base_url), encoding="utf-8"
        )
        self._vibe_home = str(home)

    def end_metering(self) -> None:
        """Stop the relay and remove the throwaway VIBE_HOME."""
        if self._relay is not None:
            self._relay.stop()
            self._relay = None
        if self._vibe_home is not None:
            shutil.rmtree(self._vibe_home, ignore_errors=True)
            self._vibe_home = None

    def _provider_flags(self) -> list[str]:
        # The throwaway VIBE_HOME has no trusted-folder record; trust the cwd for
        # this invocation so vibe does not stop to prompt.
        return [] if self._vibe_home is None else ["--trust"]

    def command(self, opening: str | None = None) -> list[str]:
        """Build the ``vibe`` command line for this run.

        Args:
            opening: The opening prompt to start the session on, or ``None``.

        Returns:
            The argv list to execute.
        """
        argv = [BINARY, *self._provider_flags()]
        if opening is not None:
            argv.append(opening)
        return argv

    def start_client(self) -> int:
        """Launch vibe, blocking until it exits.

        Injected context is written to a temporary file the agent is told to read
        first, removed when the client exits.

        Returns:
            The client's exit code.
        """
        if self.run.context is not None and not self.run.resume:
            path = context_file.write(self.run.job, self.run.session_id, self.run.context)
            return self._run(self.command(read_first_opening(str(path), self.run.kickoff)))
        return self._run(self.command(self.run.kickoff))

    def _extra_env(self) -> dict[str, str]:
        """Point vibe at the throwaway config home when the relay is running."""
        return {} if self._vibe_home is None else {"VIBE_HOME": self._vibe_home}

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


def _vibe_metered(method: str, path: str) -> bool:
    """A metered vibe turn: ``POST`` to the Chat Completions endpoint."""
    return method == "POST" and path.split("?", 1)[0].endswith("/chat/completions")
