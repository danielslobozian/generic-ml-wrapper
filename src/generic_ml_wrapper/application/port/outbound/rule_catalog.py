# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for reading the user's rules as a browsable catalogue."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.rule_group import RuleGroup


class RuleCatalogPort(ABC):
    """List the environments and roles that hold rules, with each rule's summary."""

    @abstractmethod
    def groups(self) -> tuple[RuleGroup, ...]:
        """Return every environment and role that holds at least one rule.

        Best-effort: an unreadable file is skipped rather than raised, so browsing never
        fails on one malformed rule. Groups with no rules are omitted entirely.

        Returns:
            The populated groups, environments before roles, each sorted by slug.
        """
