# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``DefaultCliCallerProvider``: config overrides first, then built-in callers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.caller.claude_cli_caller import ClaudeCliCaller
from generic_ml_wrapper.adapter.outbound.caller.codex_cli_caller import CodexCliCaller
from generic_ml_wrapper.adapter.outbound.caller.cursor_cli_caller import CursorCliCaller
from generic_ml_wrapper.adapter.outbound.caller.loader import load_caller_class
from generic_ml_wrapper.adapter.outbound.caller.vibe_cli_caller import VibeCliCaller
from generic_ml_wrapper.application.port.outbound.cli_caller import CliCaller, CliCallerProvider

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.run import RunContext
    from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
    from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
    from generic_ml_wrapper.application.port.outbound.plugin_source import PluginSourcePort
    from generic_ml_wrapper.application.port.outbound.transcript import TranscriptPort


class UnsupportedClientError(ValueError):
    """Raised when a run's client has no override and no built-in caller."""


class DefaultCliCallerProvider(CliCallerProvider):
    """Resolve a run's caller: a config override if present, else the built-in one."""

    def __init__(
        self,
        overrides: dict[str, str] | None = None,
        *,
        metering: PerTurnMeteringPort,
        transcript: TranscriptPort | None = None,
        interceptors: InterceptorChain | None = None,
        plugins: PluginSourcePort | None = None,
    ) -> None:
        """Bind the provider to its overrides, metering store, and interceptor chain.

        Args:
            overrides: A client-to-spec mapping from config; each value is a caller
                spec (``"module:Class"`` / ``"/path.py:Class"``) or a plugin id.
            metering: The per-turn store the built-in gateway callers record to. Every
                built-in client except cursor routes through a relay that records here.
            transcript: Where the relay records each call's transcript, or ``None``.
            interceptors: The interceptor chain the relay applies to wire traffic.
            plugins: Resolves a plugin-id override to a loadable spec; ``None`` means
                overrides are used verbatim (only ``"path.py:Class"`` specs work).
        """
        self._overrides = overrides or {}
        self._metering = metering
        self._transcript = transcript
        self._interceptors = interceptors
        self._plugins = plugins

    def for_run(self, run: RunContext) -> CliCaller:
        """Return the caller for the run's client.

        Args:
            run: The run to launch.

        Returns:
            A caller bound to the run — an overridden one when configured, else the
            built-in caller (every built-in but cursor routes through the relay).

        Raises:
            UnsupportedClientError: If the client has neither an override nor a
                built-in caller.
        """
        spec = self._overrides.get(run.client)
        if spec is not None:
            # A plugin-id override resolves via its manifest; a "path:Class" spec passes through.
            if self._plugins is not None:
                spec = self._plugins.resolve_caller(spec)
            return load_caller_class(spec)(run)
        if run.client == "claude":
            return ClaudeCliCaller(run, self._metering, self._interceptors, self._transcript)
        if run.client == "cursor":
            return CursorCliCaller(run)
        if run.client == "codex":
            return CodexCliCaller(run, self._metering, self._interceptors, self._transcript)
        if run.client == "vibe":
            return VibeCliCaller(run, self._metering, self._interceptors, self._transcript)
        message = f"unsupported client: {run.client!r}"
        raise UnsupportedClientError(message)
