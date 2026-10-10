# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for reading an attachment's manifest.yaml as flat ``key: value`` text."""

from __future__ import annotations

import pytest

from generic_ml_wrapper.application.domain.model.attachment import (
    AttachmentError,
    AttachmentVersion,
    AttachmentVersionError,
)
from generic_ml_wrapper.application.domain.model.identifiers import IdentifierError
from generic_ml_wrapper.application.domain.service.attachment_manifest import parse_manifest

_FULL = """\
name: workflow-creator
description: Create a checklist, step by step.
version: 1.0.0
main_md_file: main.md
"""


def test_reads_the_four_keys() -> None:
    manifest = parse_manifest(_FULL)
    assert manifest.name == "workflow-creator"
    assert manifest.description == "Create a checklist, step by step."
    assert manifest.version == AttachmentVersion(1, 0, 0)
    assert manifest.main_md_file == "main.md"


def test_description_is_optional() -> None:
    manifest = parse_manifest("name: a\nversion: 0.1.0\nmain_md_file: docs/a.md\n")
    assert manifest.description == ""
    assert manifest.main_md_file == "docs/a.md"


def test_reads_what_yaml_allows_around_flat_keys() -> None:
    text = (
        "﻿# an attachment\n"
        "\n"
        "name : 'notes'\n"
        'description: "Has: a colon"\n'
        "version: 2.10.3   # a comment\n"
        "main_md_file:main.md\r\n"
    )
    manifest = parse_manifest(text)
    assert manifest.name == "notes"
    assert manifest.description == "Has: a colon"
    assert manifest.version == AttachmentVersion(2, 10, 3)
    assert manifest.main_md_file == "main.md"


@pytest.mark.parametrize(
    ("text", "key", "params"),
    [
        ("name: a\njust text\n", "error.attachment.manifest_line", {"line": 2}),
        (": value\n", "error.attachment.manifest_line", {"line": 1}),
        ("name: a\nauthor: me\n", "error.attachment.manifest_unknown_key", {"key": "author"}),
        ("name: a\nname: b\n", "error.attachment.manifest_duplicate_key", {"key": "name"}),
        (
            "version: 1.0.0\nmain_md_file: m.md\n",
            "error.attachment.manifest_missing_key",
            {"key": "name"},
        ),
        (
            "name: a\nversion:\nmain_md_file: m.md\n",
            "error.attachment.manifest_missing_key",
            {"key": "version"},
        ),
        (
            "name: a\nversion: 1.0.0\n",
            "error.attachment.manifest_missing_key",
            {"key": "main_md_file"},
        ),
        ("", "error.attachment.manifest_missing_key", {"key": "name"}),
    ],
)
def test_refuses_what_is_not_the_flat_format(
    text: str, key: str, params: dict[str, object]
) -> None:
    with pytest.raises(AttachmentError) as raised:
        parse_manifest(text)
    assert raised.value.catalogue_key == key
    assert raised.value.params == params


def test_nesting_is_refused_as_an_unknown_key() -> None:
    with pytest.raises(AttachmentError) as raised:
        parse_manifest("name: a\nversion: 1.0.0\nmain_md_file: m.md\nextra:\n  nested: x\n")
    assert raised.value.params == {"key": "extra"}


@pytest.mark.parametrize(
    "main",
    ["/etc/passwd", "../outside.md", "a/../../b.md", "a//b.md", "./a.md", "a\\b.md", "C:x.md"],
)
def test_main_file_must_stay_inside_the_attachment(main: str) -> None:
    with pytest.raises(AttachmentError) as raised:
        parse_manifest(f"name: a\nversion: 1.0.0\nmain_md_file: {main}\n")
    assert raised.value.catalogue_key == "error.attachment.main_path"


def test_name_and_version_follow_their_rules() -> None:
    with pytest.raises(IdentifierError):
        parse_manifest("name: Bad Name\nversion: 1.0.0\nmain_md_file: m.md\n")
    with pytest.raises(AttachmentVersionError):
        parse_manifest("name: a\nversion: 1.0\nmain_md_file: m.md\n")
