# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The Session value object."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    """A named, resumable client conversation belonging to a job.

    Attributes:
        session_id: The human-readable id, ``<job>_NNN``.
        job: The job this session belongs to.
        client: The client it runs on (e.g. ``"claude"``).
        uuid: The client-side session id (Claude's ``--session-id``), or ``None``.
    """

    session_id: str
    job: str
    client: str
    uuid: str | None
