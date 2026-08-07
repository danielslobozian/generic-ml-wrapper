# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Offer the packaged starting-point roles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_role_examples import ListRoleExamplesUseCase

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.role import Role
    from generic_ml_wrapper.application.port.outbound.role_examples_repository import (
        RoleExamplesRepositoryPort,
    )


class ListRoleExamplesService(ListRoleExamplesUseCase):
    """Read the offered roles from the packaged examples."""

    def __init__(self, examples: RoleExamplesRepositoryPort) -> None:
        """Bind the use case to the examples it offers.

        Args:
            examples: Supplies the packaged starting-point roles.
        """
        self._examples = examples

    def execute(self) -> tuple[Role, ...]:
        """Return the offered roles, in display order.

        Returns:
            The offered roles, empty when none are packaged.
        """
        return self._examples.find_all()
