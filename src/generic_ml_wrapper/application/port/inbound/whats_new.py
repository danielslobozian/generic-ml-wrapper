# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for "what's new": the release notes, and the ones not yet shown."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.release_note import ReleaseNote


class WhatsNew(ABC):
    """Tell the user what changed in gmlw."""

    @abstractmethod
    def all(self) -> tuple[ReleaseNote, ...]:
        """Every release's notes, newest first; none when this copy ships no changelog."""

    @abstractmethod
    def take_unseen(self) -> tuple[ReleaseNote, ...]:
        """The releases since the notes were last shown, recorded as shown now.

        Recorded as it is read, so they are shown once: the next call returns nothing until
        the next upgrade. The first call ever returns nothing either -- there is no earlier
        version to tell what changed since -- and starts the record.

        Returns:
            The unseen releases, newest first; never raises.
        """
