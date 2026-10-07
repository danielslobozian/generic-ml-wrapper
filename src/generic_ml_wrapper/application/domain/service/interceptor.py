# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ``Interceptor`` abstraction: a text transform applied at a named target.

This is the domain-owned contract the :class:`InterceptorChain` sequences. The
outbound :class:`~generic_ml_wrapper.application.port.outbound.interceptor.InterceptorPort`
extends it, so the dependency points inward (port -> domain) and the domain never
reaches out to a port.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Interceptor(ABC):
    """Transform a piece of text flowing through gmlw at a named target."""

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
