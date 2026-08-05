# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Codex callers: launch codex, optionally through a per-turn metering relay."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.caller import codex_session_index, context_file
from generic_ml_wrapper.adapter.outbound.caller.child_process import ChildProcess
from generic_ml_wrapper.adapter.outbound.caller.context_opening import read_first_opening
from generic_ml_wrapper.adapter.outbound.gateway import openai_responses
from generic_ml_wrapper.adapter.outbound.gateway.relay import MeteringRelay
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCallerPort
from generic_ml_wrapper.application.wiring.diagnostics_log import log

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.run import RunContext
    from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
    from generic_ml_wrapper.application.port.outbound.session_store import SessionStorePort
    from generic_ml_wrapper.application.port.outbound.transcript import TranscriptPort
    from generic_ml_wrapper.application.usecase.interceptor_chain import InterceptorChain

BINARY = "codex"
# Codex's status-line items, chosen to mirror gmlw's own first line block for block
# and in the same left-to-right order:
#
#   git <repo>/<branch>  ·  folder  ·  model  ·  ctx …/<window> (<pct>%)  ·  quota 5h · wk
#   project-name,git-branch current-dir model  context-window-size,context-used
#                                                            five-hour-limit,weekly-limit
#
# Only items with a true equivalent are listed. gmlw's short sha, dirty count, the
# context numerator, the quota reset countdown and cost have no codex key and are
# absent rather than approximated: `branch-changes` is commits-vs-default-branch, not
# working-tree dirt, and `used-tokens` is session-cumulative, not window occupancy, so
# either would answer a different question than the block it stood in for.
#
# Polarity is codex's to decide — it reports the rate limits as remaining where gmlw
# shows consumed. Both say how the allowance is going, and gmlw's own rendering does
# not change to match. Fixed here, deliberately not configurable.
#
# Naming an item codex may not know is safe: it validates the *shape* of this value
# (it must be a sequence) but not the item names, so an unrecognised item is silently
# omitted rather than refused. Verified on 0.145.0 — a malformed value fails config
# loading before the terminal is even checked, while `["not-a-real-item"]` loads.
_STATUS_LINE = (
    "project-name",
    "git-branch",
    "current-dir",
    "model",
    "context-window-size",
    "context-used",
    "five-hour-limit",
    "weekly-limit",
)
# ChatGPT-sign-in upstream (the verified default). API-key mode would target
# api.openai.com with a /v1 prefix; a config-driven option is a later follow-up.
_UPSTREAM = "https://chatgpt.com"
_UPSTREAM_PREFIX = "/backend-api/codex"


class CodexCliCallerAdapter(CliCallerPort):
    """Launch codex for a run, routed through a per-turn metering relay.

    Codex has no status-line hook, so none is installed. It takes its operating
    context via a "read this file first" opening message (it has no system-prompt
    flag). ``start_metering`` stands up a relay pointed at the ChatGPT-Codex backend
    and ``_provider_flags`` adds the ``model_providers`` overrides pointing codex at
    it; if the relay cannot start, codex launches unmetered.

    Resume works the other way round from Claude's. Codex mints its own session id and
    has no flag to accept ours, so instead of *telling* it an id we *learn* the one it
    minted — off the relayed request body, on the first metered turn — then bind that
    id to the session and register the session's name in codex's own index, so the
    session can be reopened by either. A codex session is therefore resumable from its
    first turn onward, not from launch.
    """

    def __init__(
        self,
        run: RunContext,
        metering: PerTurnMeteringPort,
        interceptors: InterceptorChain | None = None,
        transcript: TranscriptPort | None = None,
        sessions: SessionStorePort | None = None,
    ) -> None:
        """Bind the caller to a run, its metering store, and the interceptor chain.

        Args:
            run: The run this caller will launch and meter.
            metering: Where the relay records per-turn usage.
            interceptors: The interceptor chain the relay applies to wire traffic.
            transcript: Where the relay records each call's transcript, or ``None``.
            sessions: Where the observed client-side session id is bound back to the
                session record; ``None`` disables learning it (the session still runs
                and meters, it just stays unresumable).
        """
        super().__init__(run)
        self._metering = metering
        self._interceptors = interceptors
        self._transcript = transcript
        self._sessions = sessions
        self._relay: MeteringRelay | None = None

    def can_meter_per_call(self) -> bool:
        """This caller records per-turn usage via its metering relay."""
        return True

    def can_resume(self) -> bool:
        """Whether this codex session can be reopened — only once its id is known.

        Overrides the catalog's flat capability: for codex, resumability is a property
        of the *session*, not the client. A session is resumable once the relay has
        learned the id codex minted for it, and only while codex still has that session
        on disk (deleting it there must not leave a resume that silently opens a new,
        empty session instead).
        """
        return self.run.uuid is not None and codex_session_index.knows(self.run.uuid)

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
            session_id_reader=openai_responses.read_session_id,
            session_id_sink=self._bind_session_id,
            interceptors=self._interceptors,
        )
        try:
            relay.start()
        except OSError as error:
            log.warning(f"metering relay failed to start ({error}); launching codex unmetered")
            return
        self._relay = relay

    def _bind_session_id(self, uuid: str) -> None:
        """Record the session id codex minted, and give codex our name for it.

        Called by the relay on the first metered turn (and again only if the id ever
        changes). Two writes, deliberately in this order: the session record is ours and
        is what ``gmlw`` resumes from, so it must land first; codex's name registry is a
        convenience on top, letting ``codex resume <job>_NNN`` work outside the wrapper.

        Runs on a relay handler thread mid-turn, so it swallows its own failures — a
        session that cannot be made resumable is a lesser loss than a broken turn.
        """
        if self._sessions is None:
            return
        try:
            self._sessions.bind_uuid(self.run.job, self.run.session_id, uuid)
        except Exception as error:  # noqa: BLE001  (bookkeeping must never break a turn)
            log.warning(
                f"could not record the client session id for {self.run.session_id} "
                f"({error}); it will not be resumable",
                key="log.session_bind_failed",
            )
            return
        codex_session_index.register(self.run.session_id, uuid)

    def end_metering(self) -> None:
        """Stop the metering relay."""
        if self._relay is not None:
            self._relay.stop()
            self._relay = None

    def _status_line_flags(self) -> list[str]:
        """Override codex's status line so it reads like the one gmlw gives claude.

        Chosen to mirror the wrapper's own line block for block, in the same order:
        branch, folder, model, context fill, then the usage windows. Cost has no codex
        key and is simply absent — codex does not know what a turn cost.

        ``context-used`` rather than ``context-remaining`` deliberately: gmlw shows
        consumption everywhere else, and a bar that reads "22% left" where the eye is
        trained on "78% used" is worse than no bar at all.

        Applied whether or not the relay came up — it is presentation, not metering —
        and passed as ``-c``, which codex layers over ``config.toml`` for this launch
        only. Nothing is written to disk, so there is nothing to restore afterwards
        (unlike claude, where the status line is installed into ``settings.json``).

        A user who wants a different line can pass their own ``-c tui.status_line=…``
        through ``[client.args]``: those arrive after these, and the last ``-c`` for a
        key wins.
        """
        items = ",".join(f'"{item}"' for item in _STATUS_LINE)
        return ["-c", f"tui.status_line=[{items}]"]

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

        On resume this is ``codex resume <id>``; the subcommand comes before the
        provider flags because ``resume`` is a subcommand, not an option. The id is
        codex's own, learned on a previous run — the session's ``<job>_NNN`` name would
        also resolve (we register it), but the id is what we hold and needs no registry
        lookup to be correct.

        Args:
            opening: The opening message to start the session on, or ``None``.

        Returns:
            The argv list to execute.
        """
        head = [BINARY, "resume", self.run.uuid] if self.run.resume and self.run.uuid else [BINARY]
        argv = [*head, *self._status_line_flags(), *self._provider_flags(), *self.run.client_args]
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
        return ChildProcess().run(argv, self.run.cwd, env)


def _codex_path_map(path: str) -> str:
    """Map codex's ``/v1/x`` (its base_url ends ``/v1``) to the backend prefix."""
    sub = path[len("/v1") :] if path.startswith("/v1") else path
    return _UPSTREAM_PREFIX + sub


def _codex_metered(method: str, path: str) -> bool:
    """A metered codex turn: ``POST`` to the Responses endpoint."""
    return method == "POST" and path.split("?", 1)[0].endswith("/responses")
