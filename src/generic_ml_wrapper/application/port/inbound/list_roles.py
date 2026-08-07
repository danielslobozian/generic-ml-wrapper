# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing the roles the user has."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.role import Role


class ListRolesUseCase(ABC):
    """List the user's stored roles."""

    @abstractmethod
    def execute(self) -> tuple[Role, ...]:
        """Return every stored role, sorted by code.

        Every one of them, including those holding no rules — this answers "what can I
        switch to", which is a different question from what the rules browser asks.

        Returns:
            The stored roles, empty when the user has none.
        """
