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
        uuid: The client-side session id — one we minted and handed to the client
            (Claude's ``--session-id``), or one the client minted and we learned off the
            wire (Codex, bound after the session's first turn) — or ``None``.
        cwd: The working directory the session was launched in, or ``None`` if unknown
            (pre-existing sessions). Claude resume is scoped to this folder, so a resume
            must relaunch there.
        resumable: Whether this session can be resumed — the client's capability at
            creation (claude/cursor yes; codex/vibe no), which for codex is only the
            starting state: it flips on once the session's own id has been learned from
            the wire and bound, so resumability there is per-session, not per-client.
        created_at: When the session was first recorded (ISO string), populated on read
            from the store; ``None`` for a freshly-minted, not-yet-persisted session.
            Excluded from equality, being store-assigned rather than app-provided.
        workflow: The workflow the session was started with, or ``None`` for a plain one.
            A job can run a different workflow in each of its sessions (a feature, then
            an MR review), so it is recorded here rather than on the job.
        attachment: The attachment the session was started with, or ``None``.
        attachment_version: That attachment's version, as ``MAJOR.MINOR.PATCH``.
        attachment_hash: The hash that version had when the session started, so the
            record says what ran even after the version is deleted.
    """

    session_id: str
    job: str
    client: str
    uuid: str | None
    cwd: str | None = None
    resumable: bool = True
    created_at: str | None = field(default=None, compare=False)
    workflow: str | None = None
    attachment: str | None = None
    attachment_version: str | None = None
    attachment_hash: str | None = None
