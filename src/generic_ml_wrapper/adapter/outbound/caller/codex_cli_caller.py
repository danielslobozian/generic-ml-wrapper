# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Codex callers: launch codex, optionally through a per-turn metering relay."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.caller import context_file
from generic_ml_wrapper.adapter.outbound.caller.context_opening import read_first_opening
from generic_ml_wrapper.adapter.outbound.gateway import openai_responses
from generic_ml_wrapper.adapter.outbound.gateway.relay import MeteringRelay
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller
from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.run import RunContext
    from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
    from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
    from generic_ml_wrapper.application.port.outbound.transcript import TranscriptPort

BINARY = "codex"
# ChatGPT-sign-in upstream (the verified default). API-key mode would target
# api.openai.com with a /v1 prefix; a config-driven option is a later follow-up.
_UPSTREAM = "https://chatgpt.com"
_UPSTREAM_PREFIX = "/backend-api/codex"


class CodexCliCaller(CliCaller):
    """Launch codex for a run, routed through a per-turn metering relay.

    Codex has no status-line hook, so none is installed. It takes its operating
    context via a "read this file first" opening message (it has no system-prompt
    flag). ``start_metering`` stands up a relay pointed at the ChatGPT-Codex backend
    and ``_provider_flags`` adds the ``model_providers`` overrides pointing codex at
    it; if the relay cannot start, codex launches unmetered.
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

    def can_resume(self) -> bool:
        """Codex mints a fresh conversation and exposes no session id to resume.

        Resuming would require scanning ``~/.codex`` for the local rollout, which
        the wrapper deliberately does not do; ``--resume-latest`` is refused for
        codex rather than silently starting a new session.
        """
        return False

    def can_meter_per_call(self) -> bool:
        """This caller records per-turn usage via its metering relay."""
        return True

    def start_metering(self) -> None:
        """Start the Codex metering relay for this session."""
        relay = MeteringRelay(
            job=self.run.job,
            session=self.run.session_id,
            metering=self._metering,
            client=self.run.client,
            transcript=self._transcript,
            upstream_base=_UPSTREAM,
            path_map=_codex_path_map,
            usage_reader=openai_responses.read_usage,
            is_metered=_codex_metered,
            interceptors=self._interceptors,
        )
        try:
            relay.start()
        except OSError as error:
            log.warning(f"metering relay failed to start ({error}); launching codex unmetered")
            return
        self._relay = relay

    def end_metering(self) -> None:
        """Stop the metering relay."""
        if self._relay is not None:
            self._relay.stop()
            self._relay = None

    def _provider_flags(self) -> list[str]:
        if self._relay is None:
            return []
        base_url = f"{self._relay.base_url}/v1"
        return [
            "-c",
            'model_providers.gml.name="gmlcache"',
            "-c",
            f'model_providers.gml.base_url="{base_url}"',
            "-c",
            'model_providers.gml.wire_api="responses"',
            "-c",
            "model_providers.gml.requires_openai_auth=true",
            "-c",
            'model_provider="gml"',
        ]

    def command(self, opening: str | None = None) -> list[str]:
        """Build the ``codex`` command line for this run.

        Args:
            opening: The opening message to start the session on, or ``None``.

        Returns:
            The argv list to execute.
        """
        argv = [BINARY, *self._provider_flags()]
        if opening is not None:
            argv.append(opening)
        return argv

    def start_client(self) -> int:
        """Launch codex, blocking until it exits.

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


def _codex_path_map(path: str) -> str:
    """Map codex's ``/v1/x`` (its base_url ends ``/v1``) to the backend prefix."""
    sub = path[len("/v1") :] if path.startswith("/v1") else path
    return _UPSTREAM_PREFIX + sub


def _codex_metered(method: str, path: str) -> bool:
    """A metered codex turn: ``POST`` to the Responses endpoint."""
    return method == "POST" and path.split("?", 1)[0].endswith("/responses")
