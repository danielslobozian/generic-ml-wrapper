# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The result of a ``config set``."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SetOutcome:
    """The result of a ``config set``.

    Attributes:
        key: The key that was set.
        old: The value before the change (the effective value, default when it was unset).
        new: The value after the change (``None`` when the key was cleared).
        changed: Whether the write actually changed the stored value.
    """

    key: str
    old: object
    new: object
    changed: bool
