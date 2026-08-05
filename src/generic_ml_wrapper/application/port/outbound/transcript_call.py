# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""One recorded call: its request, response, usage, and place in the session."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage


@dataclass(frozen=True)
class TranscriptCall:
    """One recorded call: its request, response, usage, and place in the session.

    Attributes:
        job: The job the call belongs to.
        session: The session the call belongs to.
        call_seq: The per-session call number (1-based).
        request: The request body forwarded upstream.
        response: The response body returned upstream (raw).
        usage: The turn's usage, or ``None`` if none could be read.
    """

    job: str
    session: str
    call_seq: int
    request: bytes
    response: bytes
    usage: TurnUsage | None
