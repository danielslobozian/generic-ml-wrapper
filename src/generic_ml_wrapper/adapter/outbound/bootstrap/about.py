# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A role/environment folder's ``.about.toml``: the human label + description + created.

The folder name is the code (the id); this sidecar carries what the user actually typed —
the ``label`` shown in menus and the fuller ``description`` — plus when the folder appeared.
Written missing-only, so re-running init or the code migration never clobbers it.

Reading and writing the same file live together: the two are one format, and a change to
what the sidecar holds has to land on both halves at once.
"""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

import tomlkit

if TYPE_CHECKING:
    from pathlib import Path

ABOUT = ".about.toml"


def read_about(folder: Path) -> tuple[str, str]:
    """Read ``folder/.about.toml``, falling back to the folder name for the label.

    Best-effort: an absent or unparseable sidecar yields the folder name and an empty
    description rather than raising, so one hand-edited file never breaks a listing.

    Args:
        folder: The role or environment folder.

    Returns:
        The label and the description.
    """
    about = folder / ABOUT
    if not about.is_file():
        return folder.name, ""
    try:
        data = tomllib.loads(about.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return folder.name, ""
    return str(data.get("label", folder.name)), str(data.get("description", ""))


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
