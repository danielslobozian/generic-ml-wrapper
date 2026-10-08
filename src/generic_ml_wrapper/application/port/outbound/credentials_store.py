# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the wrapper's own credentials store."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CredentialsStorePort(ABC):
    """Store and resolve per-attachment credentials the wrapper owns.

    Credentials are grouped by attachment; within an attachment each entry's name is the
    exact environment variable to export at launch, and its value is the secret.
    """

    @abstractmethod
    def resolve(self, attachment: str) -> dict[str, str]:
        """Return an attachment's credentials as an env-var-name to value mapping.

        Args:
            attachment: The attachment whose credentials to read.

        Returns:
            The mapping of environment-variable name to secret (empty if none).
        """

    @abstractmethod
    def set(self, attachment: str, name: str, value: str) -> None:
        """Store one credential for an attachment, replacing any prior value.

        Args:
            attachment: The attachment the credential belongs to.
            name: The environment-variable name to export at launch.
            value: The secret value.
        """
