# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for slug derivation, collision suffixing, and best-effort folder birth time."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.common.fs_time import created_ms
from generic_ml_wrapper.common.slug import slugify, unique_slug

if TYPE_CHECKING:
    from pathlib import Path


def test_slugify_lowercases_transliterates_and_kebab_cases() -> None:
    assert slugify("Ingénierie logicielle sénior") == "ingenierie-logicielle-senior"
    assert slugify("Work @ ACME, Inc.") == "work-acme-inc"
    assert slugify("  spaced   out  ") == "spaced-out"
    assert slugify("Éàûü") == "eauu"


def test_slugify_returns_empty_when_nothing_is_slug_worthy() -> None:
    assert slugify("***") == ""
    assert slugify("") == ""
    assert slugify("   ") == ""


def test_slugify_trims_to_max_len_on_a_word_boundary() -> None:
    result = slugify("one two three four five six seven eight", max_len=20)
    assert len(result) <= 20
    assert not result.endswith("-")
    assert result == "one-two-three-four"  # cut at the last whole word within 20 chars


def test_unique_slug_returns_the_base_when_free() -> None:
    assert unique_slug("home", {"work"}.__contains__) == "home"


def test_unique_slug_appends_the_first_free_numeric_suffix() -> None:
    taken = {"work", "work-2"}
    assert unique_slug("work", taken.__contains__) == "work-3"


def test_created_ms_returns_a_positive_stamp_for_an_existing_folder(tmp_path: Path) -> None:
    folder = tmp_path / "env"
    folder.mkdir()
    assert created_ms(folder) > 0


def test_created_ms_is_zero_for_a_missing_path(tmp_path: Path) -> None:
    assert created_ms(tmp_path / "nope") == 0
