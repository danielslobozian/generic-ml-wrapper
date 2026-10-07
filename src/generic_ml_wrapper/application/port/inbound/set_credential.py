# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for storing a workflow credential."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SetCredentialCommand:
    """A request to store one credential for a workflow.

    Attributes:
        workflow: The workflow the credential belongs to.
        name: The environment-variable name to export at launch.
        value: The secret value.
    """

    workflow: str
    name: str
    value: str


class SetCredential(ABC):
    """Store a single workflow credential in the wrapper's own store."""

    @abstractmethod
    def execute(self, command: SetCredentialCommand) -> None:
        """Store the credential described by the command.

        Args:
            command: The workflow, environment-variable name, and secret value.
        """
