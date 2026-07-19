# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for wrapping the old single-context layout into an environment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.migration import MigrationReport


class LayoutMigratorPort(ABC):
    """Relocate the old ``profile/company`` context into ``environments/<env>/``."""

    @abstractmethod
    def migrate(self, environment: str) -> MigrationReport:
        """Wrap the old place-specific context into an environment, non-destructively.

        Idempotent and keyed on the old folder's presence: once the old layout is gone
        the call is a no-op (an empty report). Nothing is overwritten — a name that
        already exists at the target is left in place and reported as skipped.

        Args:
            environment: The environment to wrap the old context into (the active one).

        Returns:
            What was moved and what was skipped (an empty report when there was nothing
            to migrate).
        """
