# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the validated identifier value objects."""

from __future__ import annotations

import pytest

from generic_ml_wrapper.application.domain.model.identifiers import (
    AttachmentName,
    EnvVarName,
    IdentifierError,
    JobId,
    TagName,
    WorkflowName,
)


@pytest.mark.parametrize("value", ["JOB-1", "JOB-123", "test_1", "a", "A9", "x" * 64])
def test_job_id_accepts_safe_segments(value: str) -> None:
    assert JobId(value) == value
    assert isinstance(JobId(value), str)


@pytest.mark.parametrize(
    "value",
    [
        "",  # empty
        "_x",  # leading underscore
        "-x",  # leading hyphen
        "a.b",  # dot (would allow ..)
        "..",  # traversal
        "a/b",  # separator
        "/abs",  # absolute
        "a\\b",  # windows separator
        "a b",  # space
        "a!",  # punctuation
        "x" * 65,  # too long
    ],
)
def test_job_id_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(IdentifierError):
        JobId(value)


@pytest.mark.parametrize("value", ["doc-review", "a", "a1", "create-workflow"])
def test_workflow_name_accepts_kebab(value: str) -> None:
    assert WorkflowName(value) == value


@pytest.mark.parametrize("value", ["", "Bad", "_common", "a b", "-x", "a_b", "a/b"])
def test_workflow_name_rejects_invalid(value: str) -> None:
    with pytest.raises(IdentifierError):
        WorkflowName(value)


@pytest.mark.parametrize("value", ["workflow-creator", "a", "a1", "notes-2"])
def test_attachment_name_accepts_kebab(value: str) -> None:
    assert AttachmentName(value) == value


@pytest.mark.parametrize("value", ["", "Bad", "_common", "a b", "-x", "a_b", "a/b", "..", "a.b"])
def test_attachment_name_rejects_invalid(value: str) -> None:
    with pytest.raises(IdentifierError):
        AttachmentName(value)


@pytest.mark.parametrize("value", ["TOKEN", "GITHUB_TOKEN", "_x", "A1", "aws_key"])
def test_env_var_name_accepts_valid(value: str) -> None:
    assert EnvVarName(value) == value


@pytest.mark.parametrize("value", ["", "1TOKEN", "A-B", "a b", "TOKEN!", "a.b"])
def test_env_var_name_rejects_invalid(value: str) -> None:
    with pytest.raises(IdentifierError):
        EnvVarName(value)


@pytest.mark.parametrize(
    ("value", "stored"),
    [
        ("sprint-42", "sprint-42"),
        ("Sprint-42", "sprint-42"),
        ("v1.2", "v1.2"),
        ("q3_okr", "q3_okr"),
    ],
)
def test_tag_name_accepts_and_lowercases(value: str, stored: str) -> None:
    assert TagName(value) == stored


@pytest.mark.parametrize("value", ["", "-lead", "has space", "#sprint", "a" * 41, "sprint/42"])
def test_tag_name_rejects(value: str) -> None:
    with pytest.raises(IdentifierError):
        TagName(value)
