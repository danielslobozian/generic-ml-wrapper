# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request to start (or resume) a session on a job."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartJobCommand:
    """A request to start (or resume) a session on a job.

    Attributes:
        job: The job identifier.
        client: The client to launch.
        resume_latest: Resume the job's most recent session instead of minting one.
        resume_session: Resume this specific session id instead of the latest; takes
            precedence over ``resume_latest``. ``None`` means "not a specific-session resume".
        workflow: A workflow to run on the job, or ``None`` for the plain wrapper.
        client_args: Passthrough launch arguments for this call, replacing whatever
            is configured for the client; ``None`` means "use the configured value".
    """

    job: str
    client: str
    resume_latest: bool = False
    resume_session: str | None = None
    workflow: str | None = None
    client_args: str | None = None
