# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""One offered menu example for an axis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AxisExample:
    """One offered menu example for an axis.

    Attributes:
        slug: The canonical (English) slug the example resolves to, language-independent.
        label_key: The catalogue key for the menu label.
        description_key: The catalogue key for the menu description.
    """

    slug: str
    label_key: str
    description_key: str
