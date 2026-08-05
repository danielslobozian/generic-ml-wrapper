# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A stderr diagnostics sink — legible for a utility command, forbidden for a session.

This is the shape gmlw shipped before there was a port: ``gmlw WARNING [JOB-1] message``
on ``stderr``, so a diagnostic is visible immediately while a person is running
``gmlw jobs`` and watching. Keep it for exactly that case.

It must **not** be wired for a run that hands the terminal to a client: there, ``stderr``
is the client's own screen, so a line written here is painted over by the client's next
redraw — visible long enough to alarm, never long enough to copy, and preserved nowhere.
That failure is issue #59, and the reason
:class:`~generic_ml_wrapper.adapter.outbound.diagnostics.rolling_file_diagnostics.RollingFileDiagnosticsAdapter`
exists.
"""

from __future__ import annotations

import sys
import traceback
from typing import IO

from generic_ml_wrapper.adapter.outbound.diagnostics import levels
from generic_ml_wrapper.adapter.outbound.diagnostics.scrub import scrub_record, scrub_text
from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort


class StderrDiagnosticsAdapter(DiagnosticsPort):
    """Write single-line diagnostics to ``stderr``."""

    def __init__(self, level: str | None = None, stream: IO[str] | None = None) -> None:
        """Bind the sink to its threshold and destination stream.

        Args:
            level: Minimum severity; records below it are dropped.
            stream: The destination stream; defaults to the live ``sys.stderr`` (resolved
                per emit, so a test or a caller that redirects it is honoured).
        """
        self._threshold = levels.threshold(level)
        self._stream = stream

    def debug(self, message: str, **context: object) -> None:
        """Emit a debug-level diagnostic."""
        self._emit(levels.DEBUG, message, None, context)

    def info(self, message: str, **context: object) -> None:
        """Emit an info-level diagnostic."""
        self._emit(levels.INFO, message, None, context)

    def warning(self, message: str, **context: object) -> None:
        """Emit a warning-level diagnostic."""
        self._emit(levels.WARNING, message, None, context)

    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None:
        """Emit an error-level diagnostic, appending *exc*'s traceback when given."""
        self._emit(levels.ERROR, message, exc, context)

    def _emit(
        self,
        level: str,
        message: str,
        exc: BaseException | None,
        context: dict[str, object],
    ) -> None:
        if levels.ORDER[level] < self._threshold:
            return
        try:
            parts = ["gmlw", level.upper(), scrub_text(message)]
            extras = "  ".join(f"{k}={v}" for k, v in scrub_record(context).items())
            line = " ".join(parts) + (f"  {extras}" if extras else "")
            if exc is not None:
                rendered = "".join(
                    traceback.format_exception(type(exc), exc, exc.__traceback__)
                ).rstrip()
                line += "\n" + scrub_text(rendered)
            print(line, file=self._stream if self._stream is not None else sys.stderr)
        except Exception:  # noqa: BLE001, S110 — the never-raises contract
            # Nowhere to report a logging failure to: the only channel is the one that
            # just failed. Swallowing is the contract, not an oversight.
            pass
