# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The MigrateLayout use case: wrap the old layout into the active environment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.migrate_layout import MigrateLayout

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.application.domain.model.migration import MigrationReport
    from generic_ml_wrapper.application.port.outbound.layout_migrator import LayoutMigratorPort


class MigrateLayoutUseCase(MigrateLayout):
    """Migrate into the *active* environment, resolved at call time.

    Kept independent of init: init persists ``default_environment`` first, so this reads it
    afterward and migrates into it. The same call catches installs that were initialised
    before migration existed — it is idempotent, a no-op once the old layout is gone.
    """

    def __init__(self, migrator: LayoutMigratorPort, environment: Callable[[], str]) -> None:
        """Wire the use case to its migrator and the active-environment resolver.

        Args:
            migrator: The outbound migrator that relocates the old layout.
            environment: Resolves the active environment (``config.default_environment``).
        """
        self._migrator = migrator
        self._environment = environment

    def execute(self) -> MigrationReport:
        """Migrate the old layout into the active environment.

        Returns:
            What was moved and skipped (an empty report when there was nothing to do).
        """
        return self._migrator.migrate(self._environment())
