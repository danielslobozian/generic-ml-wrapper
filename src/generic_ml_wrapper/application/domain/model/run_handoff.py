# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""What a launch tells the client about the run it is part of."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunHandoff:
    """The run a launched client belongs to, as the launch announced it.

    A client the wrapper launches is a separate process, and anything it calls back into
    -- the status line, most of all -- has to be told which run it is part of. This is
    that message: written by whatever performs a launch, read by whatever the client calls.

    Every field is optional because a client can be started by hand, outside any run, and
    then there is simply nothing to say.

    Attributes:
        job: The job the run belongs to, or ``None``.
        session_id: The session's ``<job>_NNN`` id, or ``None``.
        client: Which client was launched, or ``None``.
    """

    job: str | None = None
    session_id: str | None = None
    client: str | None = None
