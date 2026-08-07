# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""List the roles the user has."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_roles import ListRolesUseCase

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.role import Role
    from generic_ml_wrapper.application.port.outbound.role_repository import RoleRepositoryPort


class ListRolesService(ListRolesUseCase):
    """Read the user's roles from the repository."""

    def __init__(self, roles: RoleRepositoryPort) -> None:
        """Bind the use case to the repository it reads.

        Args:
            roles: Supplies the user's stored roles.
        """
        self._roles = roles

    def execute(self) -> tuple[Role, ...]:
        """Return every stored role, sorted by code.

        Returns:
            The stored roles, empty when the user has none.
        """
        return self._roles.find_all()
