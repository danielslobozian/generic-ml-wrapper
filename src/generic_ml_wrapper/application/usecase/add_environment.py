# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Add an environment from a typed label."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.environment import Environment
from generic_ml_wrapper.application.domain.model.environment_code_already_exists_error import (
    EnvironmentCodeAlreadyExistsError,
)
from generic_ml_wrapper.application.port.inbound.add_environment import AddEnvironmentUseCase
from generic_ml_wrapper.application.port.inbound.add_environment_result import AddEnvironmentResult

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.inbound.add_environment_command import (
        AddEnvironmentCommand,
    )
    from generic_ml_wrapper.application.port.outbound.environment_repository import (
        EnvironmentRepositoryPort,
    )


class AddEnvironmentService(AddEnvironmentUseCase):
    """Add an environment, refusing a code that is already taken.

    Creation only: an existing folder is never clobbered, so a label that reduces to a code
    someone already holds is refused rather than merged into it. Deriving the code, and
    refusing a label that leaves nothing to derive from, are the environment's own business.
    """

    def __init__(self, environments: EnvironmentRepositoryPort) -> None:
        """Bind the use case to the repository it stores into.

        Args:
            environments: Reads and stores the user's environments.
        """
        self._environments = environments

    def execute(self, command: AddEnvironmentCommand) -> AddEnvironmentResult:
        """Add the environment, refusing a code that is already taken.

        Args:
            command: The label to derive the code from, and the optional description.

        Returns:
            The stored environment.

        Raises:
            UncodableEnvironmentLabelError: If the label reduces to nothing.
            EnvironmentCodeAlreadyExistsError: If an environment already holds the derived
                code.
        """
        environment = Environment(None, command.label, command.description)
        if self._environments.exists(environment):
            raise EnvironmentCodeAlreadyExistsError(
                "error.environment.exists", code=environment.code
            )
        self._environments.save(environment)
        return AddEnvironmentResult(environment=environment)
