# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The process-wide handle on the wrapper's diagnostics.

Diagnostics are separate from command output: results and user-facing errors print to
stdout; warnings, traces and caught failures come here, and *where* here is — a rolling
file, stderr, both, or nowhere — is decided once at the composition root and never at a
call site::

    from generic_ml_wrapper.application.wiring.diagnostics_log import log

    log.warning(i18n.t("log.relay_failed", error=error), client="claude")
    log.bind(job, session).error(i18n.t("log.gateway_crashed"), exc=error)

The active sink is a
:class:`~generic_ml_wrapper.application.port.outbound.diagnostics.DiagnosticsPort`,
installed by :func:`set_active` — the same shape ``i18n.set_active`` already uses for the
active localiser, and for the same reason: threading a logger through every constructor
in the app buys nothing when there is exactly one of it per process.

**This module deliberately imports no sink.** The default below is a no-op, and the
composition root installs a real sink as its first act; nothing logs before that point.

It lives with the composition root because that is what it is: one destination chosen
once per process. **Nothing in the application ring may use it** — a use case or a domain
service that needs to report something is handed a
:class:`~generic_ml_wrapper.application.domain.service.diagnostics.Diagnostics`.

The message handed to a sink is **already localised**: resolving a catalogue key is the
caller's job (``i18n.t(...)``), so a sink stays a dumb destination.
"""

from __future__ import annotations

from dataclasses import dataclass

from generic_ml_wrapper.application.domain.service.diagnostics import Diagnostics


class _NoDiagnostics(Diagnostics):
    """The pre-wiring default: drop everything, quietly.

    Not a fallback anyone should rely on — it exists so that importing this module has
    no side effect and no adapter dependency. The composition root replaces it before
    the first command runs.
    """

    def debug(self, message: str, **context: object) -> None:
        """Discard a debug-level diagnostic."""

    def info(self, message: str, **context: object) -> None:
        """Discard an info-level diagnostic."""

    def warning(self, message: str, **context: object) -> None:
        """Discard a warning-level diagnostic."""

    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None:
        """Discard an error-level diagnostic."""


_active: Diagnostics = _NoDiagnostics()


def set_active(sink: Diagnostics) -> Diagnostics:
    """Install *sink* as the process-wide diagnostics destination.

    Args:
        sink: The sink every :class:`Log` will emit through from now on.

    Returns:
        The sink that was active before, so a caller (a test, a scoped command) can
        restore it.
    """
    global _active  # noqa: PLW0603 — one destination per process, by design
    previous = _active
    _active = sink
    return previous


def active() -> Diagnostics:
    """Return the sink currently installed."""
    return _active


@dataclass(frozen=True)
class Log:
    """A logger carrying zero or more bound context labels.

    Labels are rendered as a ``[label]`` prefix on the message, so every sink shows them
    without needing to know what they mean. They are for the identifiers that would
    otherwise be repeated into every call in a region — the job and the session.
    """

    context: tuple[str, ...] = ()

    def bind(self, *labels: str) -> Log:
        """Return a logger with additional context labels bound.

        Args:
            labels: Context labels to append (empty labels are ignored).

        Returns:
            A new ``Log`` carrying the deeper context.
        """
        return Log(self.context + tuple(label for label in labels if label))

    def debug(self, message: str, **context: object) -> None:
        """Emit a debug-level diagnostic."""
        _active.debug(self._prefixed(message), **context)

    def info(self, message: str, **context: object) -> None:
        """Emit an info-level diagnostic."""
        _active.info(self._prefixed(message), **context)

    def warning(self, message: str, **context: object) -> None:
        """Emit a warning-level diagnostic."""
        _active.warning(self._prefixed(message), **context)

    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None:
        """Emit an error-level diagnostic.

        Args:
            message: The (already localised) message.
            exc: An optional caught exception whose traceback the sink renders — the
                supported way to preserve a traceback without printing one.
            context: Free-form key/value context rendered alongside the message.
        """
        _active.error(self._prefixed(message), exc, **context)

    def _prefixed(self, message: str) -> str:
        return "".join(f"[{label}] " for label in self.context) + message


log = Log()
"""The default process logger (no bound context)."""
