# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The HookRunner: run the hooks bound to a lifecycle seam, best-effort."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.common.log import log

if TYPE_CHECKING:
    from collections.abc import Sequence

    from generic_ml_wrapper.application.domain.service.hook import Hook, HookContext, HookPhase


class HookRunner:
    """An ordered set of ``(phase, client, hook)`` entries run at named lifecycle seams.

    Each hook is bound to a phase and an optional client scope; :meth:`run` invokes, in
    declared order, those whose phase matches and whose scope is unset or equals the run's
    client. Hooks are **best-effort**: a hook that raises is logged and skipped, never
    propagating — a misconfigured or failing hook must not break a launch or its teardown.
    An empty runner is a no-op.
    """

    def __init__(self, hooks: Sequence[tuple[HookPhase, str | None, Hook]]) -> None:
        """Bind the runner to its ordered hooks.

        Args:
            hooks: The ``(phase, client, hook)`` entries, in invocation order. A
                ``client`` of ``None`` means the hook runs for every client.
        """
        self._hooks = tuple(hooks)

    def run(self, phase: HookPhase, context: HookContext) -> None:
        """Run every hook bound to ``phase`` whose client scope matches, in order.

        Args:
            phase: The lifecycle seam to run hooks for.
            context: The run facts handed to each hook (its ``phase`` matches ``phase``).
        """
        for entry_phase, client, hook in self._hooks:
            if entry_phase != phase or (client is not None and client != context.client):
                continue
            try:
                hook.run(context)
            except Exception as error:  # noqa: BLE001  a hook must never break the run
                log.warning(f"{phase} hook failed: {error}")
