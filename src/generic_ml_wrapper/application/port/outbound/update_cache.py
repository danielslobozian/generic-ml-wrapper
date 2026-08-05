# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for remembering the last check for a newer release.

Shaped around the question the application actually asks -- "what did the last check
find?" and "record this one" -- rather than around the file that happens to answer it.
A port of ``read``/``write`` would have moved the I/O one layer down without moving the
decision: the use case would still be naming a location, choosing an encoding, and
deciding what a missing file means.

Where the answer is kept, what it is written as, and what happens when it cannot be
written are the implementation's own business. In particular, *failing to record is not
an error here*: the check is an unasked-for courtesy on launch, and a cache that cannot
be written must not turn into an interruption for the user.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.update_check import UpdateCheck


class UpdateCachePort(ABC):
    """Remember the last release check, and report it back."""

    @abstractmethod
    def last_check(self) -> UpdateCheck | None:
        """Return the last recorded check, or ``None`` if there is not a usable one.

        A first run, a cache that was never written, and one that cannot be read all
        answer the same way, because the caller draws the same conclusion from each:
        there is nothing to trust, so ask again.

        Returns:
            The last check, or ``None``.
        """

    @abstractmethod
    def record(self, check: UpdateCheck) -> None:
        """Remember a check that has just completed.

        Best effort by contract: an implementation that cannot record must return
        normally rather than raise. The consequence of losing a write is one extra
        check on the next launch, which is not worth a failure the user has to see.

        Args:
            check: When the check ran, and what it found.
        """
