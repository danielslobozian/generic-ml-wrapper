# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the attachment value objects: versions, their order, the default one."""

from __future__ import annotations

import pytest

from generic_ml_wrapper.application.domain.model.attachment import (
    AttachmentVersion,
    AttachmentVersionError,
    highest,
)


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("1.0.0", (1, 0, 0)),
        ("0.0.0", (0, 0, 0)),
        ("2.1.0", (2, 1, 0)),
        ("2.10.3", (2, 10, 3)),
        ("10.20.30", (10, 20, 30)),
    ],
)
def test_version_reads_three_numbers(text: str, parts: tuple[int, int, int]) -> None:
    version = AttachmentVersion.parse(text)
    assert (version.major, version.minor, version.patch) == parts
    assert str(version) == text


@pytest.mark.parametrize(
    "text",
    [
        "",
        "2",
        "2.1",
        "1.0.0.0",
        "v1.0.0",
        "1.0.0-beta",
        "1.0.0+build",
        "1.02.0",
        "01.0.0",
        "1.0.00",
        " 1.0.0",
        "1.0.0\n",
        "1..0",
        "a.b.c",
        "\u0661.\u0660.\u0660",  # non-ASCII digits
    ],
)
def test_version_refuses_anything_else(text: str) -> None:
    with pytest.raises(AttachmentVersionError) as raised:
        AttachmentVersion.parse(text)
    assert raised.value.catalogue_key == "error.attachment.version"
    assert raised.value.params == {"value": text}


def test_versions_compare_as_numbers_not_text() -> None:
    assert AttachmentVersion.parse("2.10.0") > AttachmentVersion.parse("2.9.0")
    assert AttachmentVersion.parse("10.0.0") > AttachmentVersion.parse("9.9.9")
    assert AttachmentVersion.parse("2.0.1") > AttachmentVersion.parse("2.0.0")
    assert AttachmentVersion.parse("1.0.0") == AttachmentVersion(1, 0, 0)


def test_highest_is_the_default_even_when_a_patch_came_later() -> None:
    installed = [AttachmentVersion.parse(text) for text in ("1.0.0", "3.0.0", "2.1.0", "2.0.0")]
    assert highest(installed) == AttachmentVersion(3, 0, 0)


def test_highest_of_nothing_is_none() -> None:
    assert highest([]) is None
