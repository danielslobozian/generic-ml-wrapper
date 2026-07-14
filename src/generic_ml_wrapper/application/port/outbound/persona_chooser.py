# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for offering a persona choice on first run."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.persona import Persona


class PersonaChooserPort(ABC):
    """Offer a persona choice; declining leaves the companion off (invisible)."""

    @abstractmethod
    def choose(self, personas: list[Persona]) -> str | None:
        """Pick a persona from the offered list, or decline.

        Args:
            personas: The selectable personas to offer.

        Returns:
            The chosen persona name, or ``None`` to leave the companion off (an empty
            list, a non-interactive invocation, or the user declining all count).
        """
