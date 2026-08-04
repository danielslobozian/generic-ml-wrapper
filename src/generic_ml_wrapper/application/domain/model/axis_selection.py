# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A resolved role or environment: the slug, the label, the description."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AxisSelection:
    """A resolved role or environment.

    Role ("the functional hat") and environment ("the place work happens") are the two
    setup answers that become folders. Each is chosen from a short menu of examples or
    typed freely; the result carries the technical ``slug`` (folder + config value)
    alongside the human ``label`` and ``description`` (persisted to ``.about.toml``).

    Attributes:
        slug: The kebab-case id — the folder name and the ``[profile]`` config value.
        label: The human name shown in menus and saved to the folder's ``.about.toml``.
        description: A fuller line (the example's blurb, or the text the user typed).
    """

    slug: str
    label: str
    description: str
