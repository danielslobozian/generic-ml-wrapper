# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Fan one diagnostic out to several sinks."""

from __future__ import annotations

from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort


class TeeDiagnosticsAdapter(DiagnosticsPort):
    """Emit each record to every wrapped sink, in order.

    This is what lets "write it to the file *and* show it to me" stay a wiring decision:
    a utility command tees file + stderr, a wrapped session writes the file only, and no
    call site knows the difference.
    """

    def __init__(self, *sinks: DiagnosticsPort) -> None:
        """Bind the fan-out set.

        Args:
            sinks: The sinks to fan out to. Empty is legal and behaves as a null sink.
        """
        self._sinks = sinks

    def debug(self, message: str, **context: object) -> None:
        """Emit a debug-level diagnostic to every sink."""
        for sink in self._sinks:
            sink.debug(message, **context)

    def info(self, message: str, **context: object) -> None:
        """Emit an info-level diagnostic to every sink."""
        for sink in self._sinks:
            sink.info(message, **context)

    def warning(self, message: str, **context: object) -> None:
        """Emit a warning-level diagnostic to every sink."""
        for sink in self._sinks:
            sink.warning(message, **context)

    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None:
        """Emit an error-level diagnostic to every sink."""
        for sink in self._sinks:
            sink.error(message, exc, **context)
