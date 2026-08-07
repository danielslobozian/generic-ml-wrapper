# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the environments offered as starting points."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.environment import Environment


class ListEnvironmentExamplesUseCase(ABC):
    """Offer the packaged starting-point environments."""

    @abstractmethod
    def execute(self) -> tuple[Environment, ...]:
        """Return the offered environments, in display order.

        Returns:
            The offered environments; empty when the packaged file is missing or
            unreadable, in which case the caller simply has nothing to offer and asks for
            free text.
        """
