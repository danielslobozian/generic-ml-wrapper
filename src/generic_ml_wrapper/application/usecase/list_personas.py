# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListPersonas use case: report the selectable personas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_personas import ListPersonas

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.persona import Persona
    from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort


class ListPersonasUseCase(ListPersonas):
    """Return the selectable personas from the persona source."""

    def __init__(self, personas: PersonaSourcePort) -> None:
        """Wire the use case to its persona source.

        Args:
            personas: The source that seeds and reads personas.
        """
        self._personas = personas

    def execute(self) -> list[Persona]:
        """Return the selectable personas, sorted by name.

        Returns:
            The personas (empty if none exist).
        """
        return self._personas.available()
