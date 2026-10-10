# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for storing an attachment credential."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SetCredentialCommand:
    """A request to store one credential for an attachment.

    Attributes:
        attachment: The attachment the credential belongs to.
        name: The environment-variable name to export at launch.
        value: The secret value.
    """

    attachment: str
    name: str
    value: str


class SetCredential(ABC):
    """Store a single attachment credential in the wrapper's own store."""

    @abstractmethod
    def execute(self, command: SetCredentialCommand) -> None:
        """Store the credential described by the command.

        Args:
            command: The attachment, environment-variable name, and secret value.
        """
