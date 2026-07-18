# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ``Hook`` abstraction: an action run at a lifecycle seam bracketing a client run.

Where an :class:`~generic_ml_wrapper.application.domain.service.interceptor.Interceptor`
transforms *content* (a context section, a wire body), a hook performs an *action* at a
lifecycle *seam* — before the client launches or after it exits — and returns nothing.
This is the domain-owned contract the :class:`HookRunner` sequences; the outbound
:class:`~generic_ml_wrapper.application.port.outbound.hook.HookPort` extends it, so the
dependency points inward (port -> domain) and the domain never reaches out to a port.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class HookPhase(StrEnum):
    """The lifecycle seam a hook runs at, doubling as its config value.

    A ``str`` enum so a phase is written verbatim in ``[[hooks]]`` (``phase = "..."``).
    """

    PRE_LAUNCH = "pre-launch"  # after context compiled + caller resolved, before launch
    POST_SESSION = "post-session"  # after the client exits


@dataclass(frozen=True)
class HookContext:
    """The run facts a hook is handed — a deliberately minimal, stable view of the run.

    It exposes what a hook legitimately acts on (which client, where, which session,
    and — at ``post-session`` — how it exited) and withholds the launch-only internals
    (the compiled context, the kickoff, resolved credentials) a hook has no business
    reading.

    Attributes:
        phase: The seam this invocation is for.
        job: The job identifier.
        session_id: The session's human-readable id.
        client: The client being launched.
        uuid: The client-side session id, or ``None``.
        resume: Whether this run resumes an existing session.
        cwd: The working directory the client launches in, or ``None`` for the current
            one (a hook that needs the concrete path resolves ``None`` itself).
        exit_code: The client's exit code at ``post-session``; ``None`` at ``pre-launch``
            (the client has not run) or when the launch raised before an exit.
    """

    phase: HookPhase
    job: str
    session_id: str
    client: str
    uuid: str | None
    resume: bool
    cwd: str | None
    exit_code: int | None


class Hook(ABC):
    """Perform an action at a lifecycle seam bracketing a client run."""

    @abstractmethod
    def run(self, context: HookContext) -> None:
        """Run the hook for one seam.

        A hook is best-effort: it must never raise to break a launch (the
        :class:`HookRunner` isolates failures, but a hook should still fail quietly).
        It returns nothing — a hook acts on the world, it does not transform the run.

        Args:
            context: The run facts for this invocation, including the phase.
        """
