# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for creating a new role or environment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.create_axis_command import CreateAxisCommand
from generic_ml_wrapper.application.port.inbound.create_axis_result import CreateAxisResult

if TYPE_CHECKING:
    pass


class CreateAxisUseCase(ABC):
    """Create a new role or environment slug-folder from a typed label."""

    @abstractmethod
    def execute(self, command: CreateAxisCommand) -> CreateAxisResult:
        """Create the axis folder (and optionally make it the default).

        Args:
            command: The request describing the axis, label, description, and default flag.

        Returns:
            The outcome: the axis, the derived slug, the label, and whether it was made default.

        Raises:
            AxisLabelError: If the label is empty or slugifies to nothing.
            AxisExistsError: If a folder for the derived slug already exists.
        """
