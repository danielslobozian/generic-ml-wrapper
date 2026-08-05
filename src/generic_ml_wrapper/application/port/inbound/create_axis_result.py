# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outcome of creating an axis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.axis_kind import AxisKind


@dataclass(frozen=True)
class CreateAxisResult:
    """The outcome of creating an axis.

    Attributes:
        kind: The axis that was created.
        slug: The kebab-case id derived from the label (the folder name + config value).
        label: The human name the folder recorded.
        made_default: Whether ``profile.default_<kind>`` was pointed at the new slug.
    """

    kind: AxisKind
    slug: str
    label: str
    made_default: bool
