# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for reading, seeding, and selecting personas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.persona import Persona


class PersonaSourcePort(ABC):
    """Seed the packaged personas, list them, fetch one, and read the shared floor."""

    @abstractmethod
    def seed(self) -> None:
        """Copy the packaged default personas into the user's home, missing-only."""

    @abstractmethod
    def available(self) -> list[Persona]:
        """Return the selectable personas, sorted by name (the floor excluded).

        Returns:
            The parsed personas (empty if none exist).
        """

    @abstractmethod
    def get(self, name: str) -> Persona | None:
        """Return the named persona, or ``None`` when it does not exist.

        Args:
            name: The persona name (its file stem).

        Returns:
            The parsed persona, or ``None``.
        """

    @abstractmethod
    def floor(self) -> str:
        """Return the universal floor composed beneath every persona (or ``""``)."""
