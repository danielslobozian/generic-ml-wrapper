# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The InterceptorChain: apply per-target interceptors in order."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from generic_ml_wrapper.application.domain.service.interceptor import Interceptor


class InterceptorChain:
    """An ordered set of ``(target, interceptor)`` pairs applied at named targets.

    Each interceptor targets a name; :meth:`apply` runs, in declared order, those
    whose target matches (a target may have 0..N, and one interceptor may appear
    under several targets). The compile applies the context targets
    (``profile``/``rules``/``workflow``/``context``); the metering relay applies the
    wire targets (``request``/``response``). An empty chain is the identity.
    """

    def __init__(self, interceptors: Sequence[tuple[str, Interceptor]]) -> None:
        """Bind the chain to its ordered interceptors.

        Args:
            interceptors: The ``(target, interceptor)`` pairs, in application order.
        """
        self._interceptors = tuple(interceptors)

    def has(self, target: str) -> bool:
        """Whether any interceptor is bound to ``target``.

        Args:
            target: The target name to check.

        Returns:
            ``True`` if at least one interceptor targets it.
        """
        return any(interceptor_target == target for interceptor_target, _ in self._interceptors)

    def apply(self, target: str, text: str) -> str:
        """Apply every interceptor bound to ``target``, in order.

        Args:
            target: The target name to run interceptors for.
            text: The text to transform.

        Returns:
            The text after the matching interceptors have run.
        """
        for interceptor_target, interceptor in self._interceptors:
            if interceptor_target == target:
                text = interceptor.intercept(text, target)
        return text
