# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for diagnostics: where the wrapper's own log lines go.

The port *is* the contract. There is no second interface behind it — an abstraction the
application owns and an adapter implements is what a port already means.

Call sites pass a rendered message plus free-form keyword context that the sink formats
alongside it::

    diag.warning(loc.t("log.relay_failed", error=error), client="claude", key="relay")
    diag.error(loc.t("log.gateway_crashed"), exc=error, session=session_id)

**The message is already localised when it arrives.** Resolving a catalogue key is the
caller's job, not the sink's: a sink that resolved keys would have to know about i18n, and
a sink is meant to be a dumb destination. Pass ``key=`` alongside so the raw catalogue key
lands in the record too and logs stay greppable whatever language they were written in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DiagnosticsPort(ABC):
    """A severity-levelled sink for the wrapper's own technical diagnostics.

    Diagnostics are *not* command output: results and user-facing errors go to stdout,
    diagnostics go here. What "here" means is a wiring decision — a rolling file, stderr,
    both, or nowhere — which is precisely why this is a port. The composition root
    resolves *policy* and supplies the concrete sink, so "quiet" is a wiring choice (a
    null sink) rather than a branch at every call site.

    The distinction that motivates it: during a wrapped session ``stderr`` is the
    *client's own screen*, so a sink that writes there corrupts the client's display and
    the line is lost anyway. Utility commands have no such constraint. One contract, two
    wirings.

    **Implementations must never raise.** A diagnostics failure must not break or alter
    the run it was only observing; an emit that cannot complete is swallowed. Callers may
    therefore log from anywhere, including an ``except`` block, without guarding the log
    call itself.
    """

    @abstractmethod
    def debug(self, message: str, **context: object) -> None:
        """Emit a debug-level diagnostic. Must never raise."""

    @abstractmethod
    def info(self, message: str, **context: object) -> None:
        """Emit an info-level diagnostic. Must never raise."""

    @abstractmethod
    def warning(self, message: str, **context: object) -> None:
        """Emit a warning-level diagnostic. Must never raise."""

    @abstractmethod
    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None:
        """Emit an error-level diagnostic. Must never raise.

        Args:
            message: The (already localised) message.
            exc: An optional caught exception whose traceback the sink renders. This
                is the supported way to get a traceback into the log — and the reason
                a traceback never has to reach the user's screen to be preserved.
            context: Free-form key/value context rendered alongside the message.
        """
