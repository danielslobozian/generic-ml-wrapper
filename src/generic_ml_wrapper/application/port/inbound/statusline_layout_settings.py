# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for reading and changing the status line's layout."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.statusline_layout import StatuslineLayout


class StatuslineLayoutSettings(ABC):
    """Read and persist which status-line blocks show, in which order."""

    @abstractmethod
    def load(self) -> StatuslineLayout:
        """Return the configured layout (the full line where nothing is configured)."""

    @abstractmethod
    def save(self, layout: StatuslineLayout) -> None:
        """Persist ``layout``, keeping the rest of the config file as it is."""
