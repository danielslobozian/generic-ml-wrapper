# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A diagnostics sink that discards everything."""

from __future__ import annotations

from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort


class NullDiagnosticsAdapter(DiagnosticsPort):
    """Drop every diagnostic.

    Quiet is a *wiring* decision, not a condition each call site tests: wire this and
    nothing is written, by construction. It is the right sink wherever a stray byte
    would break something — the statusline hot path, which renders into another
    program's prompt, and any run that must leave the filesystem untouched.
    """

    def debug(self, message: str, **context: object) -> None:
        """Discard a debug-level diagnostic."""

    def info(self, message: str, **context: object) -> None:
        """Discard an info-level diagnostic."""

    def warning(self, message: str, **context: object) -> None:
        """Discard a warning-level diagnostic."""

    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None:
        """Discard an error-level diagnostic."""
