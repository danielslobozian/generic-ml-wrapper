# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the JSON-backed localiser."""

import json
from importlib import resources

from generic_ml_wrapper.common.i18n import (
    SUPPORTED_LANGUAGES,
    Localizer,
    active,
    load_localizer,
    resolve_language,
    set_active,
    t,
)


def _catalog(lang: str) -> dict[str, str]:
    path = resources.files("generic_ml_wrapper").joinpath("resources", "i18n", f"{lang}.json")
    return json.loads(path.read_text(encoding="utf-8"))


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


def test_catalogues_have_identical_key_sets() -> None:
    # The app-wide catalogue must not drift: every language carries exactly the same
    # keys, so a new user-facing string can never ship translated in one language and
    # missing in another (English fallback would mask it silently otherwise).
    english = set(_catalog("en"))
    for lang in SUPPORTED_LANGUAGES:
        assert set(_catalog(lang)) == english, f"{lang}.json keys differ from en.json"


def test_active_defaults_to_english_then_tracks_set_active() -> None:
    original = active()
    try:
        assert active().lang == "en"  # seeded to English at import
        set_active(load_localizer("fr"))
        assert active().lang == "fr"
        assert t("prompt.pick_plain", range="1-2").startswith("Choisissez")
    finally:
        set_active(original)  # never leak the language change into other tests


def test_module_level_t_uses_the_active_localiser() -> None:
    original = active()
    try:
        set_active(load_localizer("en"))
        assert t("jobs.none") == "No jobs yet. Start one with: gmlw start <job>"
    finally:
        set_active(original)
