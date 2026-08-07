# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the offered starting-point roles."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.role import Role


class RoleExamplesRepositoryPort(ABC):
    """Supply the roles offered as starting points at setup."""

    @abstractmethod
    def find_all(self) -> tuple[Role, ...]:
        """Return the offered roles, in display order.

        These are the same :class:`Role` type a stored role uses. Their label and
        description hold a catalogue key rather than typed text, which needs no flag to
        tell apart: the renderer falls back to the key itself when the catalogue has no
        entry, so a user's own typed text passes through unchanged.

        Returns:
            The offered roles, empty when the packaged file is missing or unreadable.
        """
