# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the context-source taxonomy."""

from generic_ml_wrapper.application.domain.model import context_source
from generic_ml_wrapper.application.domain.model.context_source import (
    CompileMode,
    CompressorKind,
)


def test_modes_are_their_config_keys() -> None:
    assert CompileMode.DEFAULT.value == "default"
    assert CompileMode.ATTACHMENT.value == "attachment"
    assert {mode.value for mode in CompileMode} == {"default", "attachment"}


def test_source_kinds_follow_the_data_shape() -> None:
    assert context_source.ME_USER.kind is CompressorKind.HUMAN_TOUCH
    assert context_source.ME_LEARNED.kind is CompressorKind.HUMAN_TOUCH
    assert context_source.RULES_ENVIRONMENT.kind is CompressorKind.RULES
    assert context_source.RULES_ROLE.kind is CompressorKind.RULES
    # verbatim by default — each word matters / tone must not be distorted
    assert context_source.COMPANY.kind is None
    assert context_source.PERSONA.kind is None


def test_kind_name_exposes_the_config_key() -> None:
    assert context_source.ME_USER.kind_name == "human-touch"
    assert context_source.COMPANY.kind_name is None


def test_every_source_can_be_switched_off() -> None:
    assert all(source.activatable for source in context_source.ALL_SOURCES)


def test_composed_order_is_identity_then_facts_then_reflexes() -> None:
    assert context_source.PROFILE_FAMILY == (
        context_source.PERSONA,
        context_source.ME_USER,
        context_source.ME_LEARNED,
        context_source.COMPANY,
    )
    assert context_source.ALL_SOURCES == context_source.CROSS_CUTTING
