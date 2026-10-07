# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for launching and metering a client — the CliCaller seam."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.domain.model.run import RunContext


class CliCaller(ABC):
    """Launch and meter one client run.

    One stateful instance per run: state set up in ``start_metering`` (before
    launch) is used by ``start_client`` and torn down in ``end_metering`` (after
    the client exits). ``start_client`` blocks, so quitting the client is the stop
    signal — the caller runs ``start_metering`` → ``start_client`` → ``end_metering``.
    """

    def __init__(self, run: RunContext) -> None:
        """Bind the caller to a run.

        Args:
            run: The run this caller will launch and meter.
        """
        self.run = run

    def can_deliver_statusline(self) -> bool:
        """Whether this client hosts a status line the wrapper renders into.

        ``True`` only for clients with a command-backed status-line hook (Claude
        Code, cursor-agent); ``False`` for clients that expose no such hook (Codex
        shows fixed built-ins; vibe has its own UI). The wrapper drives its
        status-line rendering only when this is ``True``. Default: ``False``.

        Returns:
            ``True`` if the wrapper can render a status line for this client.
        """
        return False

    def can_meter_per_call(self) -> bool:
        """Whether this caller records per-turn usage (e.g. via a metering gateway).

        ``True`` only for callers that route the client's traffic through a gateway
        able to read each request/response's token usage. Together with a config
        toggle this gates deep metering: it runs only when the caller can do it and
        the user asked for it. Default: ``False``.

        Returns:
            ``True`` if this caller can record per-turn usage.
        """
        return False

    def can_resume(self) -> bool:
        """Whether a session this caller created can be reopened. Default: ``False``.

        Declared by the caller, like :meth:`can_meter_per_call` and
        :meth:`can_deliver_statusline` — only the adapter knows whether its launch can
        target a session it has already run. This used to be answered by looking the
        *client name* up in the built-in catalog, which meant a caller supplied through
        ``[callers]`` or a plugin could never be resumable however capable it was: it
        was not on the list, so the wrapper decided on its behalf.

        ``--resume-latest`` is refused when this is ``False``, rather than silently
        starting a new session. The answer may also be per-session rather than
        per-client — Codex learns its own id mid-run, so it answers ``False`` until it
        has one.

        Returns:
            ``True`` if this caller can reopen a session it created.
        """
        return False

    def start_metering(self) -> None:  # noqa: B027  (optional hook; default no-op by design)
        """Set up metering before launch. Default: do nothing."""

    @abstractmethod
    def start_client(self) -> int:
        """Launch the client, blocking until it exits.

        Returns:
            The client's exit code.
        """

    def end_metering(self) -> None:  # noqa: B027  (optional hook; default no-op by design)
        """Tear down metering after the client exits. Default: do nothing."""


class CliCallerProvider(ABC):
    """Resolve the caller to use for a given run."""

    @abstractmethod
    def for_run(self, run: RunContext) -> CliCaller:
        """Return the caller instance for a run.

        Args:
            run: The run to launch.

        Returns:
            A caller bound to the run.
        """
