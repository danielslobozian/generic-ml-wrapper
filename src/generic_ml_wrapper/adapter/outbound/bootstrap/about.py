# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A role/environment folder's ``.about.toml``: the human label + description + created.

The folder name is the slug (the id); this sidecar carries what the user actually typed —
the ``label`` shown in menus and the fuller ``description`` — plus when the folder appeared.
Written missing-only, so re-running init or the slug migration never clobbers it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import tomlkit

if TYPE_CHECKING:
    from pathlib import Path

ABOUT = ".about.toml"


def write_about(folder: Path, label: str, description: str, created: str) -> None:
    """Write ``folder/.about.toml`` (label + description + created), only when absent.

    Args:
        folder: The role or environment slug-folder.
        label: The human name behind the slug.
        description: A fuller line (typed text, or the example's blurb).
        created: An ISO-8601 timestamp for when the folder was created.
    """
    about = folder / ABOUT
    if about.exists():
        return
    doc = tomlkit.document()
    doc["label"] = label
    doc["description"] = description
    doc["created"] = created
    about.write_text(tomlkit.dumps(doc), encoding="utf-8")
