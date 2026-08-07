# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for browsing the user's rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.inbound.list_rules_result import ListRulesResult


class ListRulesUseCase(ABC):
    """List the environments and roles that hold rules."""

    @abstractmethod
    def execute(self) -> ListRulesResult:
        """Return the environments and roles holding at least one rule.

        Best-effort: an unreadable file is skipped rather than raised, so browsing never
        fails on one malformed rule. Anything holding no rules is left out entirely, so a
        folder the user has never written to never appears as an empty branch to walk into.

        Returns:
            The populated environments and roles, each sorted by code. Both empty when the
            user has never recorded a rule.
        """
