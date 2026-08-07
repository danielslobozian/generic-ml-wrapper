# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Offer the packaged starting-point environments."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_environment_examples import (
    ListEnvironmentExamplesUseCase,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.environment import Environment
    from generic_ml_wrapper.application.port.outbound.environment_examples_repository import (
        EnvironmentExamplesRepositoryPort,
    )


class ListEnvironmentExamplesService(ListEnvironmentExamplesUseCase):
    """Read the offered environments from the packaged examples."""

    def __init__(self, examples: EnvironmentExamplesRepositoryPort) -> None:
        """Bind the use case to the examples it offers.

        Args:
            examples: Supplies the packaged starting-point environments.
        """
        self._examples = examples

    def execute(self) -> tuple[Environment, ...]:
        """Return the offered environments, in display order.

        Returns:
            The offered environments, empty when none are packaged.
        """
        return self._examples.find_all()
