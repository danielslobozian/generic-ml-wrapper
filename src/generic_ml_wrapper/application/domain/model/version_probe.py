# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""One first-party way to read a client's latest published version."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VersionProbe:
    """One first-party way to read a client's latest published version.

    Attributes:
        kind: How to read the fetched body — ``"text"`` (the whole body, a bare
            version string), ``"json"`` (a dotted path into the parsed JSON), or
            ``"regex"`` (the first capture group of ``selector``).
        url: The endpoint to GET.
        selector: The dotted JSON path (``kind="json"``) or the regex with one capture
            group (``kind="regex"``); ignored for ``"text"``.
        strip_prefix: A leading token to drop from the extracted value (e.g. ``"rust-v"``
            or ``"v"`` on a git tag).
    """

    kind: str
    url: str
    selector: str = ""
    strip_prefix: str = ""
