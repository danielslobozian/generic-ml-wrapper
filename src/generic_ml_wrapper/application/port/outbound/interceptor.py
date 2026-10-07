# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for an interceptor: a text transform applied at a named target."""

from __future__ import annotations

from abc import ABC

from generic_ml_wrapper.application.domain.service.interceptor import Interceptor


class InterceptorPort(Interceptor, ABC):
    """Outbound port for an interceptor; the contract is the domain :class:`Interceptor`.

    Interceptors are chained (0..N), ordered, and each targets a name: the
    compile-time context sections (``profile``, ``rules``, ``workflow``, ``context``)
    or, for clients routed through the metering relay, the live wire (``request`` for
    the outbound request body, ``response`` for the captured response body). A logger,
    a compressor, and a secret-anonymiser are all interceptors. An interceptor must be
    non-destructive on failure — it returns the text unchanged rather than raising — so
    a misconfigured interceptor never kills a compile or a turn.

    Adapters implement :meth:`Interceptor.intercept`; this port exists so the composition
    root can resolve interceptor specs to a stable outbound contract.
    """
