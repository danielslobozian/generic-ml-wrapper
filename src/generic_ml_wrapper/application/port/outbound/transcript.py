# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for recording a session's transcript: each call's in/out/usage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.transcript_call import TranscriptCall

if TYPE_CHECKING:
    pass


class TranscriptPort(ABC):
    """Persist a session's transcript -- the request, response, and usage of each call.

    This is the opt-in provenance/cost-ledger counterpart to metering: where metering
    records tokens, the transcript keeps the full request and response too, so a user
    can later see, per call, what went in, what came back, and what it cost.
    """

    @abstractmethod
    def record(self, call: TranscriptCall) -> None:
        """Persist one call's request, response, and usage."""
