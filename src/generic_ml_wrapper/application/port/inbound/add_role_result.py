# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outcome of adding a role."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.role import Role


@dataclass(frozen=True)
class AddRoleResult:
    """The outcome of adding a role.

    Attributes:
        role: The role that was stored, carrying the code derived from the label.
    """

    role: Role
