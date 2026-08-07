# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Point ``[profile] default_role`` at a role code."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.set_default_role import SetDefaultRoleUseCase

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.inbound.set_default_role_command import (
        SetDefaultRoleCommand,
    )
    from generic_ml_wrapper.application.port.outbound.config_writer import ConfigWriterPort


class SetDefaultRoleService(SetDefaultRoleUseCase):
    """Write a role code to ``[profile] default_role``."""

    def __init__(self, writer: ConfigWriterPort) -> None:
        """Bind the use case to the config writer it merges through.

        Args:
            writer: Persists ``[profile] default_role``.
        """
        self._writer = writer

    def execute(self, command: SetDefaultRoleCommand) -> None:
        """Write the code to ``[profile] default_role``.

        Args:
            command: The role code to make default.
        """
        self._writer.merge([("profile", "default_role", command.code)])
