# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the packaged starting-point roles and environments."""

from __future__ import annotations

from generic_ml_wrapper.adapter.outbound.bootstrap.json_environment_examples_repository import (
    JsonEnvironmentExamplesRepositoryAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.json_role_examples_repository import (
    JsonRoleExamplesRepositoryAdapter,
)
from generic_ml_wrapper.application.wiring.localization import load_localizer


def test_the_packaged_roles_are_offered_in_file_order() -> None:
    codes = [role.code for role in JsonRoleExamplesRepositoryAdapter().find_all()]
    assert codes == ["software-engineer", "product-owner", "qa-engineer", "tech-writer"]


def test_the_packaged_environments_are_offered_in_file_order() -> None:
    codes = [env.code for env in JsonEnvironmentExamplesRepositoryAdapter().find_all()]
    assert codes == ["work", "home", "open-source", "personal-project"]


def test_an_example_carries_catalogue_keys_that_the_localiser_resolves() -> None:
    # The label and description are keys, not text; nothing flags that, because the
    # localiser falls back to the key itself when the catalogue has no entry.
    role = JsonRoleExamplesRepositoryAdapter().find_all()[0]
    localizer = load_localizer("en")
    assert role.label == "init.role.example.engineer.label"
    assert localizer.t(role.label) == "Software engineer"
    assert localizer.t(role.description) == "Building and maintaining software."


def test_a_users_own_text_passes_through_the_localiser_unchanged() -> None:
    assert load_localizer("en").t("a health nut") == "a health nut"
