# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The Session value object."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Session:
    """A named, resumable client conversation belonging to a job.

    Attributes:
        session_id: The human-readable id, ``<job>_NNN``.
        job: The job this session belongs to.
        client: The client it runs on (e.g. ``"claude"``).
        uuid: The client-side session id (Claude's ``--session-id``), or ``None``.
        cwd: The working directory the session was launched in, or ``None`` if unknown
            (pre-existing sessions). Claude resume is scoped to this folder, so a resume
            must relaunch there.
        resumable: Whether this session can be resumed — snapshotted from the client's
            capability at creation (claude/cursor yes; codex/vibe no).
        created_at: When the session was first recorded (ISO string), populated on read
            from the store; ``None`` for a freshly-minted, not-yet-persisted session.
            Excluded from equality, being store-assigned rather than app-provided.
    """

    session_id: str
    job: str
    client: str
    uuid: str | None
    cwd: str | None = None
    resumable: bool = True
    created_at: str | None = field(default=None, compare=False)
