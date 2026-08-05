# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for browsing the user's rules by axis."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.rule_group import RuleGroup


class ListRulesUseCase(ABC):
    """List the environments and roles that hold rules."""

    @abstractmethod
    def execute(self) -> tuple[RuleGroup, ...]:
        """Return the populated rule groups.

        Returns:
            Every environment and role holding at least one rule, environments first.
            Empty when the user has never recorded one.
        """
