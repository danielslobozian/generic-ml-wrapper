# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""List the user's rules, grouped by the axis they live on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_rules import ListRules

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.rule_catalog import RuleGroup
    from generic_ml_wrapper.application.port.outbound.rule_catalog import RuleCatalogPort


class ListRulesUseCase(ListRules):
    """Read the rule catalogue for the Rules browser."""

    def __init__(self, catalog: RuleCatalogPort) -> None:
        """Bind the use case to the catalogue it reads.

        Args:
            catalog: Supplies the populated rule groups.
        """
        self._catalog = catalog

    def execute(self) -> tuple[RuleGroup, ...]:
        """Return the populated rule groups.

        Returns:
            Every environment and role holding at least one rule, environments first.
        """
        return self._catalog.groups()
