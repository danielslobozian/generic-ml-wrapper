# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing the selectable personas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.persona import Persona


class ListPersonas(ABC):
    """List the personas a run can adopt."""

    @abstractmethod
    def execute(self) -> list[Persona]:
        """Return the selectable personas, sorted by name.

        Returns:
            The personas (empty if none exist).
        """
