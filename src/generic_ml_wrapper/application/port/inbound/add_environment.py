# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for adding an environment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.inbound.add_environment_command import (
        AddEnvironmentCommand,
    )
    from generic_ml_wrapper.application.port.inbound.add_environment_result import (
        AddEnvironmentResult,
    )


class AddEnvironmentUseCase(ABC):
    """Add an environment from a typed label."""

    @abstractmethod
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
