# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for pointing the default environment at a code."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.inbound.set_default_environment_command import (
        SetDefaultEnvironmentCommand,
    )


class SetDefaultEnvironmentUseCase(ABC):
    """Point ``[profile] default_environment`` at an environment code."""

    @abstractmethod
    def execute(self, command: SetDefaultEnvironmentCommand) -> None:
        """Write the code to ``[profile] default_environment``.

        Args:
            command: The environment code to make default.
        """
