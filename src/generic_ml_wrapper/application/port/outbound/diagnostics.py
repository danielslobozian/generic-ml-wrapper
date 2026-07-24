# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for diagnostics: where the wrapper's own log lines go."""

from __future__ import annotations

from abc import ABC

from generic_ml_wrapper.application.domain.service.diagnostics import Diagnostics


class DiagnosticsPort(Diagnostics, ABC):
    """Outbound port for a diagnostics sink.

    The contract is the domain
    :class:`~generic_ml_wrapper.application.domain.service.diagnostics.Diagnostics`.
    Core emits through this port and never imports a logging library itself. The
    composition root resolves *policy* — the level, whether a file is written, whether
    stderr is also fed — and supplies the concrete sink, so "quiet" is a wiring choice
    (a null sink) rather than a branch at every call site.

    The distinction that motivates the port: during a wrapped session ``stderr`` is the
    *client's own screen*, so a sink that writes there corrupts the client's TUI and the
    line is lost anyway. Utility commands have no such constraint. One contract, two
    wirings.
    """
