# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the context-source taxonomy."""

from generic_ml_wrapper.application.domain.model import context_source
from generic_ml_wrapper.application.domain.model.context_source import (
    CompileMode,
    CompressorKind,
    includes_workflow,
)


def test_modes_are_their_config_keys() -> None:
    assert CompileMode.DEFAULT.value == "default"
    assert CompileMode.WORKFLOW.value == "workflow"
    assert CompileMode.AUTHORING.value == "authoring"


def test_only_workflow_modes_include_base_and_steps() -> None:
    assert includes_workflow(CompileMode.WORKFLOW) is True
    assert includes_workflow(CompileMode.AUTHORING) is True
    assert includes_workflow(CompileMode.DEFAULT) is False


def test_source_kinds_follow_the_data_shape() -> None:
    assert context_source.ME_USER.kind is CompressorKind.HUMAN_TOUCH
    assert context_source.ME_LEARNED.kind is CompressorKind.HUMAN_TOUCH
    assert context_source.RULES.kind is CompressorKind.RULES
    assert context_source.STEPS.kind is CompressorKind.TECHNICAL
    assert context_source.BASE.kind is CompressorKind.TECHNICAL
    # verbatim by default — each word matters / tone must not be distorted
    assert context_source.COMPANY.kind is None
    assert context_source.PERSONA.kind is None


def test_kind_name_exposes_the_config_key() -> None:
    assert context_source.ME_USER.kind_name == "human-touch"
    assert context_source.COMPANY.kind_name is None


def test_base_and_steps_are_not_activatable() -> None:
    assert context_source.BASE.activatable is False
    assert context_source.STEPS.activatable is False
    assert all(source.activatable for source in context_source.CROSS_CUTTING)


def test_composed_order_is_identity_then_facts_then_reflexes() -> None:
    assert context_source.PROFILE_FAMILY == (
        context_source.PERSONA,
        context_source.ME_USER,
        context_source.ME_LEARNED,
        context_source.COMPANY,
    )
    assert context_source.ALL_SOURCES[-2:] == (context_source.BASE, context_source.STEPS)
