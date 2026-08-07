# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for pointing the default role at a code."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.inbound.set_default_role_command import (
        SetDefaultRoleCommand,
    )


class SetDefaultRoleUseCase(ABC):
    """Point ``[profile] default_role`` at a role code."""

    @abstractmethod
    def execute(self, command: SetDefaultRoleCommand) -> None:
        """Write the code to ``[profile] default_role``.

        Args:
            command: The role code to make default.
        """
