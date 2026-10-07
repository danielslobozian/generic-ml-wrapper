# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for a hook: an action run at a lifecycle seam."""

from __future__ import annotations

from abc import ABC

from generic_ml_wrapper.application.domain.service.hook import Hook


class HookPort(Hook, ABC):
    """Outbound port for a lifecycle hook; the contract is the domain :class:`Hook`.

    Hooks are ordered (0..N) and each is bound in config to a phase — ``pre-launch``
    (after the context is compiled and the caller resolved, before the client starts)
    or ``post-session`` (after the client exits) — and an optional client scope. A
    per-client skills deployer, a cache warmer, a cleanup, a notifier are all hooks. A
    hook is best-effort: it must not raise to break a launch (the ``HookRunner`` isolates
    a failure, but a hook should fail quietly of its own accord).

    Adapters implement :meth:`Hook.run`; this port exists so the composition root can
    resolve hook specs to a stable outbound contract, the same trusted-code boundary as
    ``[[interceptors]]``, ``[callers]``, and plugins.
    """
