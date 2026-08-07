# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the user's environments: the folders under ``environments/``."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.environment import Environment


class EnvironmentRepositoryPort(ABC):
    """Read and store the user's environments, each with the rules it holds.

    The folder name is the code; the sidecar carries the human label and description; the
    ``rules/`` folder inside it carries the rules. This port is the single owner of that
    layout, so listing and creation share one place rather than each caller re-scanning.
    """

    @abstractmethod
    def find_all(self) -> tuple[Environment, ...]:
        """Return every stored environment, sorted by code.

        Best-effort on the rules: an unreadable rule file is skipped rather than raised, so
        browsing never fails on one malformed rule.

        Returns:
            One :class:`Environment` per folder, each carrying the rules it holds.
        """

    @abstractmethod
    def exists(self, environment: Environment) -> bool:
        """Whether an environment with this code is already stored.

        Args:
            environment: The environment whose code to look for.

        Returns:
            ``True`` if a folder for that code is present.
        """

    @abstractmethod
    def save(self, environment: Environment) -> None:
        """Store an environment: its folder, its empty ``rules/`` drop-zone, and its sidecar.

        Create-only in effect. The sidecar is written missing-only, so a label the user
        edited by hand is never overwritten by a later save.

        Args:
            environment: The environment to store.
        """
