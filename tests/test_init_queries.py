# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the queries the setup interview asks, one per question.

The terminal decides what it asks and in what order; these only answer "what is on
offer here". Each returns codes and domain values -- never a label, never a sentence.
"""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.authoring_mode import AuthoringMode
from generic_ml_wrapper.application.port.outbound.language_catalog import LanguageCatalogPort
from generic_ml_wrapper.application.usecase.list_authoring_modes import ListAuthoringModesService
from generic_ml_wrapper.application.usecase.list_available_languages import (
    ListAvailableLanguagesService,
)
from generic_ml_wrapper.application.wiring.composition import (
    build_list_environment_examples,
    build_list_role_examples,
)


class _Catalog(LanguageCatalogPort):
    def __init__(self, codes: list[str]) -> None:
        self.codes = codes

    def supported_languages(self) -> list[str]:
        return self.codes

    def default_language(self) -> str:
        return self.codes[0]


def test_languages_come_back_as_codes_not_names() -> None:
    # The terminal renders each code as its own endonym: a language menu is the one menu
    # that cannot be translated, because the reader has not chosen a language yet.
    assert ListAvailableLanguagesService(_Catalog(["en", "fr"])).execute() == ["en", "fr"]


def test_languages_are_whatever_the_build_packaged() -> None:
    assert ListAvailableLanguagesService(_Catalog(["es"])).execute() == ["es"]


def test_authoring_modes_are_the_whole_set_not_one_of_them() -> None:
    # The port is named for the question, so adding a third mode needs no rename.
    assert ListAuthoringModesService().execute() == [AuthoringMode.GUIDED, AuthoringMode.QUICK]


def test_role_and_environment_offer_different_examples() -> None:
    roles = [role.code for role in build_list_role_examples().execute()]
    environments = [env.code for env in build_list_environment_examples().execute()]
    assert "software-engineer" in roles
    assert "work" in environments
    assert not set(roles) & set(environments)


def test_offered_examples_carry_keys_not_prose() -> None:
    # An offered role knows the code it resolves to and the keys its words live under. The
    # words themselves are the terminal's, in whichever language it is speaking.
    for role in build_list_role_examples().execute():
        assert role.label.startswith("init.")
        assert role.description.startswith("init.")
