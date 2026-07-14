# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the wrapper's own credentials store."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CredentialsStorePort(ABC):
    """Store and resolve per-workflow credentials the wrapper owns.

    Credentials are grouped by workflow; within a workflow each entry's name is the
    exact environment variable to export at launch, and its value is the secret.
    """

    @abstractmethod
    def resolve(self, workflow: str) -> dict[str, str]:
        """Return a workflow's credentials as an env-var-name to value mapping.

        Args:
            workflow: The workflow whose credentials to read.

        Returns:
            The mapping of environment-variable name to secret (empty if none).
        """

    @abstractmethod
    def set(self, workflow: str, name: str, value: str) -> None:
        """Store one credential for a workflow, replacing any prior value.

        Args:
            workflow: The workflow the credential belongs to.
            name: The environment-variable name to export at launch.
            value: The secret value.
        """
