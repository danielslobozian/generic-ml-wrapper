# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""List the user's rules, by the environment or role that holds them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_rules import ListRulesUseCase
from generic_ml_wrapper.application.port.inbound.list_rules_result import ListRulesResult

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.environment_repository import (
        EnvironmentRepositoryPort,
    )
    from generic_ml_wrapper.application.port.outbound.role_repository import RoleRepositoryPort


class ListRulesService(ListRulesUseCase):
    """Read both repositories for the Rules browser, keeping only what holds rules."""

    def __init__(self, environments: EnvironmentRepositoryPort, roles: RoleRepositoryPort) -> None:
        """Bind the use case to the two repositories it reads.

        Args:
            environments: Supplies the user's environments and the rules they hold.
            roles: Supplies the user's roles and the rules they hold.
        """
        self._environments = environments
        self._roles = roles

    def execute(self) -> ListRulesResult:
        """Return the environments and roles holding at least one rule.

        Returns:
            The populated environments and roles, each sorted by code.
        """
        return ListRulesResult(
            environments=tuple(e for e in self._environments.find_all() if e.rules),
            roles=tuple(r for r in self._roles.find_all() if r.rules),
        )
