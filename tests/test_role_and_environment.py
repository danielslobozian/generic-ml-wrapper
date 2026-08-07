# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Role and Environment domain types: how a code is settled."""

from __future__ import annotations

import pytest

from generic_ml_wrapper.application.domain.model.environment import Environment
from generic_ml_wrapper.application.domain.model.role import Role
from generic_ml_wrapper.application.domain.model.rule import Rule
from generic_ml_wrapper.application.domain.model.uncodable_environment_label_error import (
    UncodableEnvironmentLabelError,
)
from generic_ml_wrapper.application.domain.model.uncodable_role_label_error import (
    UncodableRoleLabelError,
)


def test_a_null_code_is_derived_from_the_label() -> None:
    assert Role(None, "Code Reviewer").code == "code-reviewer"
    assert Environment(None, "Client Project").code == "client-project"


def test_accents_and_punctuation_reduce_cleanly() -> None:
    assert Role(None, "Équipe Produit").code == "equipe-produit"


def test_a_given_code_is_kept_and_never_re_derived() -> None:
    # A stored one passes both: re-deriving would rename a role whose label was hand-edited.
    role = Role("code-reviewer", "Something Else Entirely")
    assert role.code == "code-reviewer"


def test_a_label_with_nothing_codeable_is_refused() -> None:
    with pytest.raises(UncodableRoleLabelError):
        Role(None, "  !!!  ")
    with pytest.raises(UncodableEnvironmentLabelError):
        Environment(None, "***")


def test_the_description_defaults_to_empty() -> None:
    assert Role(None, "Code Reviewer").description == ""


def test_draft_count_counts_only_the_rules_switched_off() -> None:
    rules = (
        Rule(code="a", rule="one"),
        Rule(code="b", rule="two", draft=True),
        Rule(code="c", rule="three", draft=True),
    )
    assert Role("r", "R", "", rules).draft_count == 2
    assert Environment("e", "E", "", rules).draft_count == 2


def test_a_role_with_no_rules_holds_none() -> None:
    assert Role(None, "Code Reviewer").rules == ()
