# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Add a role from a typed label."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.role import Role
from generic_ml_wrapper.application.domain.model.role_code_already_exists_error import (
    RoleCodeAlreadyExistsError,
)
from generic_ml_wrapper.application.port.inbound.add_role import AddRoleUseCase
from generic_ml_wrapper.application.port.inbound.add_role_result import AddRoleResult

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.inbound.add_role_command import AddRoleCommand
    from generic_ml_wrapper.application.port.outbound.role_repository import RoleRepositoryPort


class AddRoleService(AddRoleUseCase):
    """Add a role, refusing a code that is already taken.

    Creation only: an existing folder is never clobbered, so a label that reduces to a code
    someone already holds is refused rather than merged into it. Deriving the code, and
    refusing a label that leaves nothing to derive from, are the role's own business.
    """

    def __init__(self, roles: RoleRepositoryPort) -> None:
        """Bind the use case to the repository it stores into.

        Args:
            roles: Reads and stores the user's roles.
        """
        self._roles = roles

    def execute(self, command: AddRoleCommand) -> AddRoleResult:
        """Add the role, refusing a code that is already taken.

        Args:
            command: The label to derive the code from, and the optional description.

        Returns:
            The stored role.

        Raises:
            UncodableRoleLabelError: If the label reduces to nothing.
            RoleCodeAlreadyExistsError: If a role already holds the derived code.
        """
        role = Role(None, command.label, command.description)
        if self._roles.exists(role):
            raise RoleCodeAlreadyExistsError("error.role.exists", code=role.code)
        self._roles.save(role)
        return AddRoleResult(role=role)
