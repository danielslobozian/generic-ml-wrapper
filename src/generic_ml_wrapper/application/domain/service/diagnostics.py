# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ``Diagnostics`` abstraction: severity-levelled technical logging.

This is the domain-owned contract every diagnostics sink implements. The outbound
:class:`~generic_ml_wrapper.application.port.outbound.diagnostics.DiagnosticsPort`
extends it, so the dependency points inward (port -> domain) and the domain never
reaches out to a port — the same shape as :class:`.interceptor.Interceptor`.

Call sites pass a rendered message plus free-form keyword context that the sink
formats alongside it::

    diag.warning(i18n.t("log.relay_failed", error=error), client="claude", key="relay")
    diag.error(i18n.t("log.gateway_crashed"), exc=error, session=session_id)

**The message is already localised when it arrives.** Resolving a catalogue key is
the caller's job, not the sink's: a sink that resolved keys would have to know about
i18n, and a sink is meant to be a dumb destination. Pass ``key=`` alongside so the
raw catalogue key lands in the record too and logs stay greppable whatever language
they were written in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Diagnostics(ABC):
    """A severity-levelled sink for the wrapper's own technical diagnostics.

    Diagnostics are *not* command output: results and user-facing errors go to
    stdout, diagnostics go here. What "here" means is a wiring decision — a rolling
    file, stderr, both, or nowhere — which is precisely why this is an abstraction.

    **Implementations must never raise.** A diagnostics failure must not break or
    alter the run it was only observing; an emit that cannot complete is swallowed.
    Callers may therefore log from anywhere, including an ``except`` block, without
    guarding the log call itself.
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
