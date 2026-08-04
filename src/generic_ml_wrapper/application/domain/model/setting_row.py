# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""One registered setting's metadata: what it is called, what it accepts, what it means."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingRow:
    """One registered setting's metadata, for rendering help and ``config list``.

    Attributes:
        key: The dotted key (e.g. ``profile.default_role``).
        type_name: A short type label (``str``/``bool``/``choice``/``str?``).
        default: The schema default.
        choices: The allowed values, or ``None`` when unconstrained.
        description: A one-line description.
    """

    key: str
    type_name: str
    default: object
    choices: tuple[str, ...] | None
    description: str
