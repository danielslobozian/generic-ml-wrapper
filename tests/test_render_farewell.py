# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the parting line, and for what it calls you when you have not said."""

from __future__ import annotations

from generic_ml_wrapper.adapter.outbound.i18n.json_catalog_localizer import (
    JsonCatalogLocalizerFactory,
)
from generic_ml_wrapper.application.domain.model.companion_settings import CompanionSettings
from generic_ml_wrapper.application.port.inbound.application_settings import (
    ApplicationSettingsUseCase,
)
from generic_ml_wrapper.application.port.outbound.system_info import SystemInfoPort
from generic_ml_wrapper.application.usecase.render_farewell import RenderFarewellService


class _Settings(ApplicationSettingsUseCase):
    def __init__(self, persona: str | None, name: str | None) -> None:
        self._companion = CompanionSettings(persona=persona, name=name)

    def companion(self) -> CompanionSettings:
        return self._companion

    def hints_enabled(self) -> bool:
        raise NotImplementedError

    def resolve_client(self, explicit: str | None) -> str:
        raise NotImplementedError

    def setup_needed(self) -> bool:
        raise NotImplementedError


class _System(SystemInfoPort):
    def __init__(self, username: str = "ada") -> None:
        self._username = username

    def username(self) -> str:
        return self._username

    def platform_name(self) -> str:
        return "Linux"


def _use_case(
    persona: str | None, name: str | None, username: str = "ada"
) -> RenderFarewellService:
    return RenderFarewellService(
        _Settings(persona, name), _System(username), JsonCatalogLocalizerFactory().load("en")
    )


def test_no_companion_means_no_goodbye() -> None:
    assert _use_case(persona=None, name="Ada").execute() is None


def test_the_configured_name_is_used() -> None:
    assert _use_case(persona="butler", name="Ada").execute() == "Bye, Ada."


def test_the_account_name_is_the_fallback() -> None:
    """A rule about the product, so it is decided here rather than by whoever prints it."""
    assert _use_case(persona="butler", name=None, username="ada").execute() == "Bye, ada."
