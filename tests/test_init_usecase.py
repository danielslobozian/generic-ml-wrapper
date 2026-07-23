# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Init use case: the ordered forced-setup interview."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.axis import AxisPrompt, AxisSelection
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.port.outbound.axis_chooser import AxisChooserPort
from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
from generic_ml_wrapper.application.port.outbound.client_setup import ClientSetupPort
from generic_ml_wrapper.application.port.outbound.language_chooser import LanguageChooserPort
from generic_ml_wrapper.application.port.outbound.layout_seeder import (
    InitPersist,
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
    def __init__(self, *, fresh: bool = True, overwrites: tuple[str, ...] = ()) -> None:
        self.selections: InitSelections | None = None
        self._fresh = fresh
        self._overwrites = overwrites

    def ensure(self, default_client: str | None = None, persona: str | None = None) -> None:
        raise AssertionError("init must not call ensure")

    def initialize(self, selections: InitSelections) -> InitPersist:
        self.selections = selections
        return InitPersist(fresh=self._fresh, overwrites=self._overwrites)


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
    """Return a scripted answer per header, else the default; record the i18n lang."""

    def __init__(self, answers: dict[str, str] | None = None) -> None:
        self._answers = answers or {}
        self.calls: list[tuple[str, str, str | None]] = []

    def ask(self, header: str, default: str, i18n: Localizer | None = None) -> str:
        self.calls.append((header, default, i18n.lang if i18n else None))
        return self._answers.get(header, default)


class _RecordingAxisChooser(AxisChooserPort):
    """Decline to the passed default (slug = default); record the prompt and i18n lang."""

    def __init__(self) -> None:
        self.calls: list[tuple[AxisPrompt, str, str | None]] = []

    def choose(
        self, prompt: AxisPrompt, default: str, i18n: Localizer | None = None
    ) -> AxisSelection:
        self.calls.append((prompt, default, i18n.lang if i18n else None))
        return AxisSelection(default, default, default)


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


_KEEP_FOUND = object()  # sentinel: emulate the "lone installed client is taken" default


class _FakeClientSetup(ClientSetupPort):
    """Record the found clients + language; return a preset choice or the lone default."""

    def __init__(self, choice: object = _KEEP_FOUND) -> None:
        self._choice = choice
        self.found: list[str] | None = None
        self.lang: str | None = None

    def choose(self, found: list[str], i18n: Localizer | None = None) -> str | None:
        self.found = found
        self.lang = i18n.lang if i18n else None
        if self._choice is _KEEP_FOUND:
            return found[0] if found else None
        return self._choice  # type: ignore[return-value]


def _use_case(  # noqa: PLR0913  (mirrors the wired ports; all defaulted)
    *,
    language: str = "en",
    found: list[str] | None = None,
    client_choice: object = _KEEP_FOUND,
    persona: str | None = None,
    text_prompt: _RecordingTextPrompt | None = None,
    seeder: _RecordingSeeder | None = None,
    default_name: str = "ada",
) -> tuple[
    InitUseCase, _RecordingSeeder, _FakeClientSetup, _RecordingTextPrompt, _RecordingAxisChooser
]:
    seeder = seeder or _RecordingSeeder()
    client_setup = _FakeClientSetup(client_choice)
    text = text_prompt or _RecordingTextPrompt()
    axis = _RecordingAxisChooser()
    use_case = InitUseCase(
        detector=_FakeDetector([] if found is None else found),
        seeder=seeder,
        language_chooser=_FakeLanguageChooser(language),
        text_prompt=text,
        axis_chooser=axis,
        personas=_FakePersonas(),
        persona_chooser=_FakePersonaChooser(persona),
        client_setup=client_setup,
        localizer_factory=load_localizer,
        languages=["en", "fr"],
        default_language="en",
        default_name=default_name,
        version="0.4.0",
    )
    return use_case, seeder, client_setup, text, axis


def test_runs_every_step_and_persists_the_selections() -> None:
    use_case, seeder, _, _, _ = _use_case(
        language="fr", found=["cursor"], persona="butler", default_name="daniel"
    )
    outcome = use_case.execute()
    assert (outcome.language, outcome.name) == ("fr", "daniel")
    assert (outcome.role.slug, outcome.environment.slug) == ("default", "work")
    assert outcome.persona == "butler"
    assert outcome.client == "cursor"  # the guided setup settled on the installed client
    assert outcome.fresh is True
    # The very same selections are handed to the seeder to persist.
    assert seeder.selections is not None
    assert seeder.selections.version == "0.4.0"
    assert seeder.selections.language == "fr"
    assert seeder.selections.role.slug == "default"
    assert seeder.selections.client == "cursor"


def test_defaults_flow_through_when_nothing_is_typed() -> None:
    use_case, seeder, _, text, axis = _use_case(default_name="ada")
    outcome = use_case.execute()
    # name falls to its default (the one free-text step); role/environment default via the
    # axis chooser, in order.
    assert [default for _, default, _ in text.calls] == ["ada"]
    assert [default for _, default, _ in axis.calls] == ["default", "work"]
    assert (outcome.name, outcome.role.slug, outcome.environment.slug) == ("ada", "default", "work")
    assert outcome.client is None  # nothing installed
    assert outcome.found == []
    assert seeder.selections is not None
    assert seeder.selections.persona is None


def test_reprompts_in_the_chosen_language_after_the_language_step() -> None:
    # Pick French first; the localiser handed to every later prompt must speak French.
    use_case, _, client_setup, text, axis = _use_case(
        language="fr", found=["claude", "cursor"], client_choice="cursor"
    )
    use_case.execute()
    assert {lang for _, _, lang in text.calls} == {"fr"}  # the name step in fr
    assert {lang for _, _, lang in axis.calls} == {"fr"}  # role + environment in fr
    assert client_setup.lang == "fr"  # and the guided client step too


def test_client_setup_receives_the_found_clients_and_its_choice_wins() -> None:
    use_case, _, client_setup, _, _ = _use_case(found=["claude", "cursor"], client_choice="cursor")
    outcome = use_case.execute()
    assert client_setup.found == ["claude", "cursor"]
    assert outcome.client == "cursor"


def test_legacy_install_reports_not_fresh() -> None:
    use_case, _, _, _, _ = _use_case(seeder=_RecordingSeeder(fresh=False))
    assert use_case.execute().fresh is False
