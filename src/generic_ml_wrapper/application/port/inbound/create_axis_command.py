# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A request to create a new role or environment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.axis_kind import AxisKind


@dataclass(frozen=True)
class CreateAxisCommand:
    """A request to create a new role or environment.

    Attributes:
        kind: Which axis to create (role or environment).
        label: The human name the user typed; the slug is derived from it.
        description: An optional fuller line saved to the folder's ``.about.toml``.
        make_default: Also point ``profile.default_<kind>`` at the new slug.
    """

    kind: AxisKind
    label: str
    description: str = ""
    make_default: bool = False
