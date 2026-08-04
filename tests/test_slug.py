# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Slug value object: derivation and collision suffixing."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.slug import Slug


def test_slugify_lowercases_transliterates_and_kebab_cases() -> None:
    assert Slug.of("Ingénierie logicielle sénior").value == "ingenierie-logicielle-senior"
    assert Slug.of("Work @ ACME, Inc.").value == "work-acme-inc"
    assert Slug.of("  spaced   out  ").value == "spaced-out"
    assert Slug.of("Éàûü").value == "eauu"


def test_slugify_returns_empty_when_nothing_is_slug_worthy() -> None:
    assert Slug.of("***").value == ""
    assert Slug.of("").value == ""
    assert Slug.of("   ").value == ""


def test_slugify_trims_to_max_len_on_a_word_boundary() -> None:
    result = Slug.of("one two three four five six seven eight", max_len=20).value
    assert len(result) <= 20
    assert not result.endswith("-")
    assert result == "one-two-three-four"  # cut at the last whole word within 20 chars


def test_unique_slug_returns_the_base_when_free() -> None:
    assert Slug("home").unique_among({"work"}.__contains__).value == "home"


def test_unique_slug_appends_the_first_free_numeric_suffix() -> None:
    taken = {"work", "work-2"}
    assert Slug("work").unique_among(taken.__contains__).value == "work-3"


def test_a_slug_renders_as_its_text() -> None:
    assert f"{Slug.of('Work @ ACME')}" == "work-acme"
