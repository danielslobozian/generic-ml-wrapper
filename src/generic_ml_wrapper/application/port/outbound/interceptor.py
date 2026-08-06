# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for an interceptor: a text transform applied at a named target.

The port *is* the contract. There is no second interface behind it — an abstraction the
application owns and an adapter implements is what a port already means.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class InterceptorPort(ABC):
    """Transform a piece of text flowing through gmlw at a named target.

    Interceptors are chained (0..N), ordered, and each targets a name: the compile-time
    context sections (``profile``, ``rules``, ``workflow``, ``context``) or, for clients
    routed through the metering relay, the live wire (``request`` for the outbound request
    body, ``response`` for the captured response body). A logger, a compressor, and a
    secret-anonymiser are all interceptors. An interceptor must be non-destructive on
    failure — it returns the text unchanged rather than raising — so a misconfigured
    interceptor never kills a compile or a turn.
    """

    @abstractmethod
    def intercept(self, text: str, target: str) -> str:
        """Return the transformed text (or the input unchanged).

        Args:
            text: The text to transform.
            target: The target it is running for (e.g. ``context``, ``request``,
                ``response``), so one interceptor can behave per target.

        Returns:
            The transformed text.
        """
