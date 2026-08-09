# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the JSON-backed message source, the locale holder and the accessor."""

import json
from collections.abc import Iterator
from importlib import resources

import pytest

from generic_ml_wrapper.adapter.inbound.common.i18n.json_catalog_message_source import (
    CATALOG_FOLDER,
    CATALOG_SUFFIX,
    JsonCatalogMessageSource,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.language_change_interceptor import (
    LanguageChangeInterceptor,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.language_code import LanguageCode
from generic_ml_wrapper.adapter.inbound.common.i18n.language_context_holder import (
    LanguageContextHolder,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
    MessageSourceAccessor,
    get_active,
    get_message,
    set_active,
)
from generic_ml_wrapper.application.domain.model.identifier_error import IdentifierError
from generic_ml_wrapper.application.domain.model.job_id import JobId
from generic_ml_wrapper.application.domain.model.workflow_name import WorkflowName

SHIPPED = JsonCatalogMessageSource().available_languages()


def _catalog(language: str) -> dict[str, str]:
    path = resources.files("generic_ml_wrapper").joinpath(
        "resources", CATALOG_FOLDER, f"{language}{CATALOG_SUFFIX}"
    )
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def restore_locale() -> Iterator[None]:
    original_locale, original_accessor = LanguageContextHolder.get_language(), get_active()
    yield
    LanguageContextHolder.set_language(original_locale)
    set_active(original_accessor)


def test_a_key_with_no_params_renders_its_template() -> None:
    assert JsonCatalogMessageSource().get_message("jobs.none", "en").startswith("No jobs yet")


def test_a_key_with_params_interpolates_them() -> None:
    rendered = JsonCatalogMessageSource().get_message("prompt.pick_plain", "en", range="1-3")
    assert "1-3" in rendered


def test_an_unknown_key_renders_as_itself() -> None:
    assert JsonCatalogMessageSource().get_message("missing.key", "en") == "missing.key"


def test_a_missing_param_falls_back_to_the_raw_template() -> None:
    source = JsonCatalogMessageSource()
    assert "{" in source.get_message("prompt.pick_plain", "en")


def test_available_languages_are_discovered_from_the_resources_folder() -> None:
    assert set(JsonCatalogMessageSource().available_languages()) == set(SHIPPED)
    assert "en" in SHIPPED


def test_a_language_with_no_catalogue_renders_the_keys_themselves() -> None:
    source = JsonCatalogMessageSource()
    assert source.get_message("prompt.pick_plain", "de", range="1-2") == "prompt.pick_plain"


def test_every_english_key_resolves_in_every_shipped_language() -> None:
    source = JsonCatalogMessageSource()
    for language in SHIPPED:
        for key in _catalog("en"):
            rendered = source.get_message(key, language, range="1-2", default=1, reply="x")
            assert rendered != key, f"{language}: {key} fell through to the raw key"


def test_catalogues_have_identical_key_sets() -> None:
    english = set(_catalog("en"))
    for language in SHIPPED:
        assert set(_catalog(language)) == english, f"{language}.json keys differ from en.json"


def test_the_holder_starts_on_english_and_tracks_what_is_set(restore_locale: None) -> None:
    LanguageContextHolder.set_language("en")
    assert LanguageContextHolder.get_language() == "en"
    LanguageContextHolder.set_language("fr")
    assert LanguageContextHolder.get_language() == "fr"


def test_an_accessor_pinned_to_a_language_ignores_the_holder(restore_locale: None) -> None:
    french = MessageSourceAccessor(JsonCatalogMessageSource(), "fr")
    LanguageContextHolder.set_language("en")
    assert "Choisissez" in french.get_message("prompt.pick_plain", range="1-2")


def test_one_accessor_follows_the_holder_when_the_language_changes(restore_locale: None) -> None:
    accessor = MessageSourceAccessor(JsonCatalogMessageSource())
    LanguageContextHolder.set_language("en")
    assert accessor.get_message("prompt.pick_plain", range="1-2").startswith("Pick")
    LanguageContextHolder.set_language("fr")
    assert accessor.get_message("prompt.pick_plain", range="1-2").startswith("Choisissez")


def test_the_module_level_call_renders_through_the_active_accessor(restore_locale: None) -> None:
    LanguageContextHolder.set_language("en")
    assert get_message("jobs.none") == "No jobs yet. Start one with: gmlw start <job>"
    LanguageContextHolder.set_language("fr")
    assert get_message("jobs.none") != "No jobs yet. Start one with: gmlw start <job>"


def test_a_two_letter_iso_code_is_a_language() -> None:
    assert LanguageCode.is_language("es")
    assert LanguageCode.is_language("de")


def test_something_that_is_not_a_language_is_rejected() -> None:
    assert not LanguageCode.is_language("zz")
    assert not LanguageCode.is_language("eng")
    assert not LanguageCode.is_language("")


def test_a_posix_locale_reduces_to_its_language() -> None:
    assert LanguageCode.from_posix_locale("fr_FR.UTF-8") == "fr"
    assert LanguageCode.from_posix_locale("de_DE") == "de"
    assert LanguageCode.from_posix_locale("en") == "en"


def test_a_posix_locale_naming_no_language_reduces_to_nothing() -> None:
    assert LanguageCode.from_posix_locale("zz_ZZ.UTF-8") is None
    assert LanguageCode.from_posix_locale(None) is None
    assert LanguageCode.from_posix_locale("") is None


# ── the in-form name hints must describe the validator that actually runs ──
# These two keys once shared the same sentence, but they guard different rules: a job id
# allows underscores and either case, a workflow name is lowercase kebab. The workflow
# hint promised underscores the validator then rejected, which reads to the user as the
# app being broken rather than the input being wrong.
def test_the_workflow_name_hint_does_not_promise_what_the_validator_rejects() -> None:
    for language in SHIPPED:
        hint = _catalog(language)["tui.wf.invalid"].lower()
        with pytest.raises(IdentifierError):
            WorkflowName("a_b")  # the validator rejects underscores…
        assert "underscore" not in hint, f"{language}: hint still offers underscores"
        assert "_" not in hint, f"{language}: hint still offers underscores"


def test_the_job_id_hint_still_offers_underscores_because_job_ids_allow_them() -> None:
    # The other half of the pair: this one was always right and must not be "fixed" too.
    assert JobId("a_b") == "a_b"
    for language in SHIPPED:
        assert "underscore" in _catalog(language)["tui.newjob.invalid"].lower(), language


def test_writing_the_language_setting_moves_the_holder(restore_locale: None) -> None:
    LanguageContextHolder.set_language("en")
    assert LanguageChangeInterceptor.after_setting_written("language.code", "fr")
    assert LanguageContextHolder.get_language() == "fr"


def test_writing_the_same_language_reports_no_change(restore_locale: None) -> None:
    LanguageContextHolder.set_language("fr")
    assert not LanguageChangeInterceptor.after_setting_written("language.code", "fr")


def test_writing_another_setting_leaves_the_holder_alone(restore_locale: None) -> None:
    LanguageContextHolder.set_language("en")
    assert not LanguageChangeInterceptor.after_setting_written("logging.level", "debug")
    assert LanguageContextHolder.get_language() == "en"


def test_clearing_the_language_setting_returns_to_the_default(restore_locale: None) -> None:
    LanguageContextHolder.set_language("fr")
    assert LanguageChangeInterceptor.after_setting_written("language.code", None)
    assert LanguageContextHolder.get_language() == "en"
