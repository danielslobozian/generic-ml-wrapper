# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``LayoutMigratorPort``: wrap ``profile/company`` into ``environments/<env>``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.migration import MigrationReport
from generic_ml_wrapper.application.port.outbound.layout_migrator import LayoutMigratorPort

if TYPE_CHECKING:
    from pathlib import Path

# The old single place-specific context folder, relative to the home root.
_OLD_COMPANY = ("profile", "company")
_ENVIRONMENTS = "environments"


class FilesystemLayoutMigrator(LayoutMigratorPort):
    """Move the old ``~/.gmlw/profile/company`` context into ``environments/<env>``."""

    def __init__(self, home: Path) -> None:
        """Bind the migrator to the runtime home directory.

        Args:
            home: The ``~/.gmlw`` root the old and new layouts live under.
        """
        self._home = home

    def migrate(self, environment: str) -> MigrationReport:
        """Relocate ``profile/company`` into ``environments/<environment>``, once.

        A move (``rename``) within the one ``~/.gmlw`` filesystem: atomic, and the content
        is preserved, not copied. A target that already carries a same-named entry is never
        overwritten — that source entry is left in ``profile/company`` and reported. The
        emptied ``profile/company`` is removed so no install is left on the old layout.

        Args:
            environment: The environment to wrap the old context into.

        Returns:
            The names moved and skipped (empty when there was nothing to migrate).
        """
        old = self._home.joinpath(*_OLD_COMPANY)
        if not old.is_dir():
            return MigrationReport(environment=environment)
        target = self._home / _ENVIRONMENTS / environment
        target.mkdir(parents=True, exist_ok=True)
        moved: list[str] = []
        skipped: list[str] = []
        for entry in sorted(old.iterdir()):
            destination = target / entry.name
            if destination.exists():
                skipped.append(entry.name)  # never overwrite; leave the source in place
            else:
                entry.rename(destination)
                moved.append(entry.name)
        if not any(old.iterdir()):  # fully drained -> retire the old layout
            old.rmdir()
        return MigrationReport(environment=environment, moved=moved, skipped=skipped)
