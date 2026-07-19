# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the JSON-backed localiser."""

from generic_ml_wrapper.common.i18n import (
    SUPPORTED_LANGUAGES,
    Localizer,
    load_localizer,
    resolve_language,
)


def test_t_returns_template_without_params() -> None:
    assert Localizer("en", {"greet": "Hello"}).t("greet") == "Hello"


def test_t_formats_params() -> None:
    assert Localizer("en", {"pick": "Pick [{range}]"}).t("pick", range="1-3") == "Pick [1-3]"


def test_t_unknown_key_returns_the_key() -> None:
    assert Localizer("en", {}).t("missing.key") == "missing.key"


def test_t_missing_param_falls_back_to_the_raw_template() -> None:
    assert Localizer("en", {"x": "{a}-{b}"}).t("x", a="1") == "{a}-{b}"


def test_resolve_language_from_a_posix_lang() -> None:
    assert resolve_language("fr_FR.UTF-8") == "fr"


def test_resolve_language_unset_defaults_to_english() -> None:
    assert resolve_language(None) == "en"


def test_resolve_language_unsupported_defaults_to_english() -> None:
    assert resolve_language("de_DE.UTF-8") == "en"


def test_supported_languages() -> None:
    assert SUPPORTED_LANGUAGES == ("en", "fr")


def test_load_localizer_french_uses_the_translation() -> None:
    french = load_localizer("fr")
    assert french.lang == "fr"
    assert "Choisissez" in french.t("prompt.pick_plain", range="1-2")


def test_load_localizer_english_is_the_base() -> None:
    english = load_localizer("en")
    assert english.t("prompt.pick_plain", range="1-2") == "Pick a number [1-2]: "


def test_load_localizer_unknown_language_falls_back_to_english() -> None:
    # No de.json exists, so the catalogue is the English base and keys still resolve.
    german = load_localizer("de")
    assert german.t("prompt.pick_plain", range="1-2") == "Pick a number [1-2]: "


def test_load_localizer_falls_back_to_english_for_a_missing_translation() -> None:
    # Every English key must resolve to real copy in French — never the raw key —
    # because the French catalogue is merged over the English base.
    french = load_localizer("fr")
    for key in load_localizer("en").__dict__["_catalog"]:
        assert french.t(key, range="1-2", default=1, reply="x") != key
