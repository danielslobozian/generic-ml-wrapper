# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the one-shot slug migration of role/environment folders."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.migration import SlugMigrationReport


class MigrateSlugs(ABC):
    """Rename legacy raw-named role/environment folders to clean slugs, once."""

    @abstractmethod
    def execute(self) -> SlugMigrationReport:
        """Run the slug migration.

        Returns:
            The ``(old, new)`` rename pairs (empty when there was nothing to migrate).
        """
