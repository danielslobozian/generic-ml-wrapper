# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the RenderGreeting use case."""

from __future__ import annotations

from datetime import datetime

from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.domain.model.workspace import Workspace
from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort
from generic_ml_wrapper.application.port.outbound.workspace import WorkspaceInspectorPort
from generic_ml_wrapper.application.usecase.render_greeting import RenderGreetingUseCase
from generic_ml_wrapper.common.config import CompanionSettings

_GREETING = "{daypart}, {name}.{repo_note} How may I be of service?"


class _Personas(PersonaSourcePort):
    def __init__(self, greeting: str = _GREETING) -> None:
        self._greeting = greeting

    def seed(self) -> None:
        pass

    def available(self) -> list[Persona]:
        return []

    def get(self, name: str) -> Persona | None:
        return Persona(name, "d", self._greeting, "b") if name == "butler" else None

    def floor(self) -> str:
        return ""


class _Workspace(WorkspaceInspectorPort):
    def __init__(self, repo: str | None = "gmlw") -> None:
        self._repo = repo

    def inspect(self) -> Workspace:
        return Workspace(folder="~/x", repo=self._repo, branch="main", short_sha="a", dirty=0)


def _use_case(
    settings: CompanionSettings,
    *,
    hour: int = 9,
    greeting: str = _GREETING,
    username: str = "os_user",
    repo: str | None = "gmlw",
) -> RenderGreetingUseCase:
    return RenderGreetingUseCase(
        personas=_Personas(greeting),
        companion=lambda: settings,
        workspace=_Workspace(repo),
        clock=lambda: datetime(2026, 7, 15, hour, 0),
        username=lambda: username,
    )


def test_off_when_no_persona_selected() -> None:
    assert _use_case(CompanionSettings(persona=None, name=None)).execute() is None


def test_off_when_persona_unknown() -> None:
    assert _use_case(CompanionSettings(persona="ghost", name=None)).execute() is None


def test_off_when_persona_has_no_greeting() -> None:
    assert (
        _use_case(CompanionSettings(persona="butler", name=None), greeting="  ").execute() is None
    )


def test_renders_with_configured_name_daypart_and_repo() -> None:
    out = _use_case(CompanionSettings(persona="butler", name="Daniel"), hour=20).execute()
    assert out == "Good evening, Daniel. You're in gmlw (main). How may I be of service?"


def test_name_falls_back_to_the_os_user() -> None:
    out = _use_case(CompanionSettings(persona="butler", name=None), username="dslobozian").execute()
    assert out is not None
    assert "dslobozian" in out


def test_repo_note_absent_outside_a_repo() -> None:
    out = _use_case(CompanionSettings(persona="butler", name="Dan"), repo=None).execute()
    assert out == "Good morning, Dan. How may I be of service?"
