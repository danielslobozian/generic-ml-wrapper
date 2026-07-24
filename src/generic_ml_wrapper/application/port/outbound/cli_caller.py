# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for launching and metering a client — the CliCaller seam."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.domain.model import client_catalog
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
        """Whether this client can resume a prior session, from the client catalog.

        ``True`` for clients whose launch can reopen a session we named/identified
        (Claude / cursor-agent ``--resume``); ``False`` for those that mint their own id
        we can't target (Codex, Vibe). ``--resume-latest`` is refused when this is
        ``False`` rather than silently starting a new session. The catalog's
        ``resumable`` flag is the single source of truth.

        Returns:
            ``True`` if this caller can resume a prior session.
        """
        info = client_catalog.by_name(self.run.client)
        return info is not None and info.resumable

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
