# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A moment the connection to a client's API failed during a session."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IncidentKind(StrEnum):
    """What went wrong.

    Attributes:
        CONNECTION_LOST: A request could not be completed; the client was sent a ``502``
            and retries on its own.
        STREAM_INTERRUPTED: An answer was cut off part way; what had arrived was kept.
    """

    CONNECTION_LOST = "connection_lost"
    STREAM_INTERRUPTED = "stream_interrupted"


@dataclass(frozen=True)
class Incident:
    """One connection failure, tied to the session it happened in.

    Attributes:
        job: The job the session belongs to.
        session_id: The session it happened in.
        kind: What went wrong.
        cause: The failure in one line, e.g. ``TimeoutError: The read operation timed out``.
        occurred_at: When it happened (epoch seconds).
    """

    job: str
    session_id: str
    kind: IncidentKind
    cause: str
    occurred_at: float
