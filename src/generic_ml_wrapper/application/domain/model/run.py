# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The RunContext handed to a client caller."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunContext:
    """Everything a caller needs to launch and meter one run.

    Attributes:
        job: The job identifier.
        session_id: The session's human-readable id.
        client: The client to launch.
        uuid: The client-side session id, or ``None``.
        resume: Whether this run resumes an existing session.
        cwd: The working directory to launch in, or ``None`` for the current one.
        context: Operating context to inject into the session, or ``None``.
        kickoff: An opening message to start the session on, or ``None``.
        env: Extra environment variables to export for the run (name/value pairs),
            e.g. a workflow's resolved credentials.
        client_args: Extra launch arguments to hand the client verbatim, already split
            into tokens. Opaque to the wrapper: whatever the user configured for this
            client, passed through unexamined. Empty when none is configured.
    """

    job: str
    session_id: str
    client: str
    uuid: str | None
    resume: bool
    cwd: str | None = None
    context: str | None = None
    kickoff: str | None = None
    env: tuple[tuple[str, str], ...] = ()
    client_args: tuple[str, ...] = ()
