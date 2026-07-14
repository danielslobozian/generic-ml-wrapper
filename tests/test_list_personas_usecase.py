# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ListPersonas use case, driven by a fake source."""

from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort
from generic_ml_wrapper.application.usecase.list_personas import ListPersonasUseCase


class _FakePersonas(PersonaSourcePort):
    def __init__(self, personas: list[Persona]) -> None:
        self._personas = personas

    def seed(self) -> None:
        raise NotImplementedError

    def available(self) -> list[Persona]:
        return self._personas

    def get(self, name: str) -> Persona | None:
        raise NotImplementedError

    def floor(self) -> str:
        raise NotImplementedError


def test_lists_the_source_personas() -> None:
    personas = [Persona("plain", "Neutral.", "", "body")]
    assert ListPersonasUseCase(_FakePersonas(personas)).execute() == personas
