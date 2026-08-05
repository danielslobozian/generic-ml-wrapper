# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The UpdateCheck value object: when the release check last ran, and what it found."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class UpdateCheck:
    """A completed check for a newer release -- when it happened, and its answer.

    Travels in both directions across
    :class:`~generic_ml_wrapper.application.port.outbound.update_cache.UpdateCachePort`:
    handed out as "this is what was last found", handed back as "record this one". It
    carries no notion of where any of that is kept, which is the whole point -- the
    application asks what the last check said, never where the answer is stored.

    Attributes:
        checked_at: When the check ran.
        latest: The newest version it found published.
    """

    checked_at: datetime
    latest: str

    def __post_init__(self) -> None:
        """Reject a check that records no answer."""
        if not self.latest:
            message = "latest must not be empty"
            raise ValueError(message)
