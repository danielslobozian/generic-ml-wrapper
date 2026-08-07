# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""List the environments the user has."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_environments import ListEnvironmentsUseCase

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.environment import Environment
    from generic_ml_wrapper.application.port.outbound.environment_repository import (
        EnvironmentRepositoryPort,
    )


class ListEnvironmentsService(ListEnvironmentsUseCase):
    """Read the user's environments from the repository."""

    def __init__(self, environments: EnvironmentRepositoryPort) -> None:
        """Bind the use case to the repository it reads.

        Args:
            environments: Supplies the user's stored environments.
        """
        self._environments = environments

    def execute(self) -> tuple[Environment, ...]:
        """Return every stored environment, sorted by code.

        Returns:
            The stored environments, empty when the user has none.
        """
        return self._environments.find_all()
