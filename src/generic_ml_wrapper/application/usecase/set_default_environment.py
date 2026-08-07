# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Point ``[profile] default_environment`` at an environment code."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.set_default_environment import (
    SetDefaultEnvironmentUseCase,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.inbound.set_default_environment_command import (
        SetDefaultEnvironmentCommand,
    )
    from generic_ml_wrapper.application.port.outbound.config_writer import ConfigWriterPort


class SetDefaultEnvironmentService(SetDefaultEnvironmentUseCase):
    """Write an environment code to ``[profile] default_environment``."""

    def __init__(self, writer: ConfigWriterPort) -> None:
        """Bind the use case to the config writer it merges through.

        Args:
            writer: Persists ``[profile] default_environment``.
        """
        self._writer = writer

    def execute(self, command: SetDefaultEnvironmentCommand) -> None:
        """Write the code to ``[profile] default_environment``.

        Args:
            command: The environment code to make default.
        """
        self._writer.merge([("profile", "default_environment", command.code)])
