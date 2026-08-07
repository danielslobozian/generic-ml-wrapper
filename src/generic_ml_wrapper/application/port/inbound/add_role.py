# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for adding a role."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.inbound.add_role_command import AddRoleCommand
    from generic_ml_wrapper.application.port.inbound.add_role_result import AddRoleResult


class AddRoleUseCase(ABC):
    """Add a role from a typed label."""

    @abstractmethod
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
