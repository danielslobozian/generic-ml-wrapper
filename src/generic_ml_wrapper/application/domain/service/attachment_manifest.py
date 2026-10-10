# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Read an attachment's ``manifest.yaml``.

The manifest is four flat ``key: value`` lines, so it is read here as text rather than
through a YAML library: blank lines and ``#`` comments are skipped, a value may be
quoted, and anything else -- an unknown key, a repeated one, nesting -- is refused rather
than guessed at.
"""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.attachment import (
    AttachmentError,
    AttachmentManifest,
    AttachmentVersion,
)
from generic_ml_wrapper.application.domain.model.identifiers import AttachmentName

#: The manifest's file name, at the root of every attachment.
MANIFEST = "manifest.yaml"

_REQUIRED = ("name", "version", "main_md_file")
_KEYS = frozenset({*_REQUIRED, "description"})
_QUOTES = ("'", '"')
_BOM = "﻿"


def parse_manifest(text: str) -> AttachmentManifest:
    """Read a manifest's text.

    Args:
        text: The content of ``manifest.yaml``.

    Returns:
        The manifest.

    Raises:
        AttachmentError: If a line is not ``key: value``, a key is unknown or repeated, a
            required key is missing or empty, or the main file's path leaves the
            attachment.
        IdentifierError: If the name is not lowercase kebab.
        AttachmentVersionError: If the version is not ``MAJOR.MINOR.PATCH``.
    """
    values: dict[str, str] = {}
    for number, raw in enumerate(text.removeprefix(_BOM).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, colon, value = line.partition(":")
        key = key.strip()
        if not colon or not key:
            raise AttachmentError("error.attachment.manifest_line", line=number)
        if key not in _KEYS:
            raise AttachmentError("error.attachment.manifest_unknown_key", key=key)
        if key in values:
            raise AttachmentError("error.attachment.manifest_duplicate_key", key=key)
        values[key] = _value(value)
    for key in _REQUIRED:
        if not values.get(key):
            raise AttachmentError("error.attachment.manifest_missing_key", key=key)
    main = values["main_md_file"]
    if not _inside(main):
        raise AttachmentError("error.attachment.main_path", file=main)
    return AttachmentManifest(
        name=AttachmentName(values["name"]),
        version=AttachmentVersion.parse(values["version"]),
        description=values.get("description", ""),
        main_md_file=main,
    )


def _value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] in _QUOTES and value[-1] == value[0]:  # noqa: PLR2004
        return value[1:-1]
    comment = value.find(" #")
    return value if comment < 0 else value[:comment].rstrip()


def _inside(path: str) -> bool:
    """Whether a manifest path stays inside the attachment: relative, ``/``-separated."""
    if path.startswith("/") or "\\" in path or (len(path) > 1 and path[1] == ":"):
        return False
    return all(part not in ("", ".", "..") for part in path.split("/"))
