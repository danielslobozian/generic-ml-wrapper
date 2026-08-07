# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the roles offered as starting points."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.role import Role


class ListRoleExamplesUseCase(ABC):
    """Offer the packaged starting-point roles."""

    @abstractmethod
    def execute(self) -> tuple[Role, ...]:
        """Return the offered roles, in display order.

        Returns:
            The offered roles; empty when the packaged file is missing or unreadable, in
            which case the caller simply has nothing to offer and asks for free text.
        """
