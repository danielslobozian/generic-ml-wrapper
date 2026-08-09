# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request to start a fresh session on a job that already exists."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StartNewSessionCommand:
    """A request to start a fresh session on a job that already exists.

    Attributes:
        job: The job to file the session under. It must already exist — starting no
            longer brings a job into being as a side effect.
        client: The client to launch, already resolved from the flag or the config.
        workflow: A workflow to run on the job, or ``None`` for the plain wrapper.
        client_args: Passthrough launch arguments replacing whatever is configured for
            the client; ``None`` uses the configured value.
    """

    job: str
    client: str
    workflow: str | None = None
    client_args: str | None = None
