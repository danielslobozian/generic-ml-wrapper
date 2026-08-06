# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The HookContext: the run facts a hook is handed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.hook_phase import HookPhase


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
