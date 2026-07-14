# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the FirstRunInit use case: detect, choose, seed."""

from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.port.inbound.first_run_init import FirstRunOutcome
from generic_ml_wrapper.application.port.outbound.client_chooser import ClientChooserPort
from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
from generic_ml_wrapper.application.port.outbound.layout_seeder import LayoutSeederPort
from generic_ml_wrapper.application.port.outbound.persona_chooser import PersonaChooserPort
from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort
from generic_ml_wrapper.application.usecase.first_run_init import FirstRunInitUseCase

_PERSONAS = [Persona("plain", "Neutral.", "", "b"), Persona("butler", "A Jeeves.", "", "b")]


class _FakeDetector(ClientDetectorPort):
    def __init__(self, found: list[str]) -> None:
        self._found = found

    def available(self) -> list[str]:
        return self._found


class _RecordingSeeder(LayoutSeederPort):
    def __init__(self) -> None:
        self.calls = 0
        self.client: str | None = None
        self.persona: str | None = None

    def ensure(self, default_client: str | None = None, persona: str | None = None) -> None:
        self.calls += 1
        self.client = default_client
        self.persona = persona


class _FakeChooser(ClientChooserPort):
    def __init__(self, choice: str | None) -> None:
        self._choice = choice
        self.asked: list[str] | None = None

    def choose(self, candidates: list[str]) -> str | None:
        self.asked = candidates
        return self._choice


class _FakePersonas(PersonaSourcePort):
    def seed(self) -> None:
        pass

    def available(self) -> list[Persona]:
        return _PERSONAS

    def get(self, name: str) -> Persona | None:
        raise NotImplementedError

    def floor(self) -> str:
        raise NotImplementedError


class _FakePersonaChooser(PersonaChooserPort):
    def __init__(self, choice: str | None) -> None:
        self._choice = choice
        self.offered: list[str] | None = None

    def choose(self, personas: list[Persona]) -> str | None:
        self.offered = [persona.name for persona in personas]
        return self._choice


def _run(
    found: list[str], choice: str | None = None, persona: str | None = None
) -> tuple[FirstRunOutcome, _FakeChooser, _RecordingSeeder]:
    seeder = _RecordingSeeder()
    chooser = _FakeChooser(choice)
    outcome = FirstRunInitUseCase(
        detector=_FakeDetector(found),
        seeder=seeder,
        chooser=chooser,
        personas=_FakePersonas(),
        persona_chooser=_FakePersonaChooser(persona),
    ).execute()
    assert seeder.calls == 1  # the layout is always seeded exactly once
    return (outcome, chooser, seeder)


def test_single_client_becomes_the_default_without_asking() -> None:
    outcome, chooser, seeder = _run(["cursor"])
    assert outcome.chosen == "cursor"
    assert chooser.asked is None  # never prompted for a lone client
    assert seeder.client == "cursor"


def test_no_client_seeds_without_a_default() -> None:
    outcome, chooser, seeder = _run([])
    assert outcome.chosen is None
    assert chooser.asked is None
    assert seeder.client is None  # commented template; built-in default applies


def test_several_clients_defer_to_the_chooser() -> None:
    outcome, chooser, seeder = _run(["claude", "cursor", "codex"], choice="cursor")
    assert chooser.asked == ["claude", "cursor", "codex"]
    assert outcome.chosen == "cursor"
    assert seeder.client == "cursor"


def test_several_clients_with_a_declined_choice_seed_no_default() -> None:
    outcome, _chooser, seeder = _run(["claude", "cursor"], choice=None)
    assert outcome.chosen is None
    assert seeder.client is None  # non-interactive: never block, keep the built-in default


def test_chosen_persona_is_offered_and_seeded() -> None:
    outcome, _chooser, seeder = _run(["cursor"], persona="butler")
    assert outcome.persona == "butler"
    assert seeder.persona == "butler"


def test_declined_persona_seeds_none() -> None:
    outcome, _chooser, seeder = _run(["cursor"], persona=None)
    assert outcome.persona is None
    assert seeder.persona is None  # companion stays off
