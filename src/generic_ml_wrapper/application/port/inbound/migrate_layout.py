# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for wrapping the old layout into the active environment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.migration import MigrationReport


class MigrateLayout(ABC):
    """Migrate the old ``profile/company`` layout into the active environment, if present."""

    @abstractmethod
    def execute(self) -> MigrationReport:
        """Run the migration against the active environment and report what it did.

        Returns:
            What was moved and skipped (an empty report when there was nothing to do).
        """
