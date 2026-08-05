# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for storing a workflow credential."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.set_credential_command import SetCredentialCommand


class SetCredentialUseCase(ABC):
    """Store a single workflow credential in the wrapper's own store."""

    @abstractmethod
    def execute(self, command: SetCredentialCommand) -> None:
        """Store the credential described by the command.

        Args:
            command: The workflow, environment-variable name, and secret value.
        """
