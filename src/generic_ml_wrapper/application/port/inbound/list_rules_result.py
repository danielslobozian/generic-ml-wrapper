# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The environments and roles that hold rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.environment import Environment
    from generic_ml_wrapper.application.domain.model.role import Role


@dataclass(frozen=True)
class ListRulesResult:
    """The environments and roles that hold rules.

    Two lists rather than one, because an environment and a role are different things. The
    browser walks the environments first — that is the order the two lists are shown in,
    not a claim about precedence.

    Attributes:
        environments: The environments holding at least one rule, sorted by code.
        roles: The roles holding at least one rule, sorted by code.
    """

    environments: tuple[Environment, ...]
    roles: tuple[Role, ...]
