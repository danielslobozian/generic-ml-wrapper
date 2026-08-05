# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""One setting's current value alongside its registry metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SettingView:
    """One setting's current value alongside its registry metadata.

    Attributes:
        key: The dotted key (e.g. ``profile.default_role``).
        value: The current effective value (the default when unset).
        default: The schema default.
        type_name: A short type label (``str``/``bool``/``choice``/``str?``).
        choices: The allowed values, or ``None`` when unconstrained.
        description: A one-line description.
    """

    key: str
    value: object
    default: object
    type_name: str
    choices: tuple[str, ...] | None
    description: str
