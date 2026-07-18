# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Init use case: the ordered forced-setup interview."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.port.outbound.client_chooser import ClientChooserPort
from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
from generic_ml_wrapper.application.port.outbound.language_chooser import LanguageChooserPort
from generic_ml_wrapper.application.port.outbound.layout_seeder import (
    InitSelections,
    LayoutSeederPort,
)
from generic_ml_wrapper.application.port.outbound.persona_chooser import PersonaChooserPort
from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort
from generic_ml_wrapper.application.port.outbound.text_prompt import TextPromptPort
from generic_ml_wrapper.application.usecase.init import InitUseCase
from generic_ml_wrapper.common.i18n import Localizer, load_localizer

_PERSONAS = [Persona("plain", "Neutral.", "", "b"), Persona("butler", "A Jeeves.", "", "b")]


class _FakeDetector(ClientDetectorPort):
    def __init__(self, found: list[str]) -> None:
        self._found = found

    def available(self) -> list[str]:
        return self._found


class _RecordingSeeder(LayoutSeederPort):
    def __init__(self, *, fresh: bool = True) -> None:
        self.selections: InitSelections | None = None
        self._fresh = fresh

    def ensure(self, default_client: str | None = None, persona: str | None = None) -> None:
        raise AssertionError("init must not call ensure")

    def initialize(self, selections: InitSelections) -> bool:
        self.selections = selections
        return self._fresh


class _FakeLanguageChooser(LanguageChooserPort):
    def __init__(self, choice: str) -> None:
        self._choice = choice
        self.offered: list[str] | None = None
        self.default: str | None = None

    def choose(self, languages: list[str], default: str) -> str:
        self.offered = languages
        self.default = default
        return self._choice


class _RecordingTextPrompt(TextPromptPort):
    """Return a scripted answer per header key, else the default; record the i18n lang."""

    def __init__(self, answers: dict[str, str] | None = None) -> None:
        self._answers = answers or {}
        self.calls: list[tuple[str, str, str | None]] = []

    def ask(self, header: str, default: str, i18n: Localizer | None = None) -> str:
        self.calls.append((header, default, i18n.lang if i18n else None))
        return self._answers.get(header, default)


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
        self.lang: str | None = None

    def choose(self, personas: list[Persona], i18n: Localizer | None = None) -> str | None:
        self.lang = i18n.lang if i18n else None
        return self._choice


class _FakeClientChooser(ClientChooserPort):
    def __init__(self, choice: str | None) -> None:
        self._choice = choice
        self.asked: list[str] | None = None
        self.lang: str | None = None

    def choose(self, candidates: list[str], i18n: Localizer | None = None) -> str | None:
        self.asked = candidates
        self.lang = i18n.lang if i18n else None
        return self._choice


def _use_case(  # noqa: PLR0913  (mirrors the wired ports; all defaulted)
    *,
    language: str = "en",
    found: list[str] | None = None,
    client_choice: str | None = None,
    persona: str | None = None,
    text_prompt: _RecordingTextPrompt | None = None,
    seeder: _RecordingSeeder | None = None,
    default_name: str = "ada",
) -> tuple[InitUseCase, _RecordingSeeder, _FakeClientChooser, _RecordingTextPrompt]:
    seeder = seeder or _RecordingSeeder()
    client_chooser = _FakeClientChooser(client_choice)
    text = text_prompt or _RecordingTextPrompt()
    use_case = InitUseCase(
        detector=_FakeDetector([] if found is None else found),
        seeder=seeder,
        language_chooser=_FakeLanguageChooser(language),
        text_prompt=text,
        personas=_FakePersonas(),
        persona_chooser=_FakePersonaChooser(persona),
        client_chooser=client_chooser,
        localizer_factory=load_localizer,
        languages=["en", "fr"],
        default_language="en",
        default_name=default_name,
        version="0.4.0",
    )
    return use_case, seeder, client_chooser, text


def test_runs_every_step_and_persists_the_selections() -> None:
    use_case, seeder, _, _ = _use_case(
        language="fr", found=["cursor"], persona="butler", default_name="daniel"
    )
    outcome = use_case.execute()
    assert (outcome.language, outcome.name, outcome.role, outcome.environment) == (
        "fr",
        "daniel",
        "default",
        "work",
    )
    assert outcome.persona == "butler"
    assert outcome.client == "cursor"  # a lone installed client is taken silently
    assert outcome.fresh is True
    # The very same selections are handed to the seeder to persist.
    assert seeder.selections is not None
    assert seeder.selections.version == "0.4.0"
    assert seeder.selections.language == "fr"
    assert seeder.selections.client == "cursor"


def test_defaults_flow_through_when_nothing_is_typed() -> None:
    use_case, seeder, _, text = _use_case(default_name="ada")
    outcome = use_case.execute()
    # name/role/environment fall to their defaults; the three free-text steps ran in order.
    assert [default for _, default, _ in text.calls] == ["ada", "default", "work"]
    assert (outcome.name, outcome.role, outcome.environment) == ("ada", "default", "work")
    assert outcome.client is None  # nothing installed
    assert outcome.found == []
    assert seeder.selections is not None
    assert seeder.selections.persona is None


def test_reprompts_in_the_chosen_language_after_the_language_step() -> None:
    # Pick French first; the localiser handed to every later prompt must speak French.
    use_case, _, client_chooser, text = _use_case(
        language="fr", found=["claude", "cursor"], client_choice="cursor"
    )
    use_case.execute()
    assert {lang for _, _, lang in text.calls} == {"fr"}  # name/role/environment all in fr
    assert client_chooser.lang == "fr"  # and the client tie-break too


def test_several_clients_go_through_the_chooser() -> None:
    use_case, _, client_chooser, _ = _use_case(found=["claude", "cursor"], client_choice="cursor")
    outcome = use_case.execute()
    assert client_chooser.asked == ["claude", "cursor"]
    assert outcome.client == "cursor"


def test_legacy_install_reports_not_fresh() -> None:
    use_case, _, _, _ = _use_case(seeder=_RecordingSeeder(fresh=False))
    assert use_case.execute().fresh is False
