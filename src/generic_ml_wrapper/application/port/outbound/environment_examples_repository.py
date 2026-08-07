# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the offered starting-point environments."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.environment import Environment


class EnvironmentExamplesRepositoryPort(ABC):
    """Supply the environments offered as starting points at setup."""

    @abstractmethod
    def find_all(self) -> tuple[Environment, ...]:
        """Return the offered environments, in display order.

        These are the same :class:`Environment` type a stored environment uses. Their label
        and description hold a catalogue key rather than typed text, which needs no flag to
        tell apart: the renderer falls back to the key itself when the catalogue has no
        entry, so a user's own typed text passes through unchanged.

        Returns:
            The offered environments, empty when the packaged file is missing or unreadable.
        """
