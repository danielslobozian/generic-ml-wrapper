# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for a hook: an action run at a lifecycle seam.

The port *is* the contract. There is no second interface behind it — an abstraction the
application owns and an adapter implements is what a port already means.

Where an :class:`~generic_ml_wrapper.application.port.outbound.interceptor.InterceptorPort`
transforms *content*, a hook performs an *action* at a lifecycle *seam* — before the client
launches or after it exits — and returns nothing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.hook_context import HookContext


class HookPort(ABC):
    """Perform an action at a lifecycle seam bracketing a client run.

    Hooks are ordered (0..N) and each is bound in config to a phase — ``pre-launch``
    (after the context is compiled and the caller resolved, before the client starts) or
    ``post-session`` (after the client exits) — and an optional client scope. A per-client
    skills deployer, a cache warmer, a cleanup, a notifier are all hooks. The composition
    root resolves hook specs to this contract, the same trusted-code boundary as
    ``[[interceptors]]``, ``[callers]``, and plugins.
    """

    @abstractmethod
    def run(self, context: HookContext) -> None:
        """Run the hook for one seam.

        A hook is best-effort: it must never raise to break a launch (the ``HookRunner``
        isolates failures, but a hook should still fail quietly). It returns nothing — a
        hook acts on the world, it does not transform the run.

        Args:
            context: The run facts for this invocation, including the phase.
        """
