# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The MigrateSlugs use case: rename legacy role/environment folders to clean slugs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.migrate_slugs import MigrateSlugs

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.migration import SlugMigrationReport
    from generic_ml_wrapper.application.port.outbound.slug_migrator import SlugMigratorPort


class MigrateSlugsUseCase(MigrateSlugs):
    """Run the slug migrator. Kept independent of init (runs after it, idempotently)."""

    def __init__(self, migrator: SlugMigratorPort) -> None:
        """Wire the use case to its migrator.

        Args:
            migrator: The outbound migrator that renames raw-named folders to slugs.
        """
        self._migrator = migrator

    def execute(self) -> SlugMigrationReport:
        """Rename legacy role/environment folders to slugs.

        Returns:
            What was renamed (an empty report when there was nothing to do).
        """
        return self._migrator.migrate()
