# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for renaming legacy raw-named role/environment folders to slugs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.migration import SlugMigrationReport


class SlugMigratorPort(ABC):
    """Rename existing ``environments/*`` and ``profile/roles/*`` folders to clean slugs."""

    @abstractmethod
    def migrate(self) -> SlugMigrationReport:
        """Rename any raw-named role/environment folder to its slug, once.

        For each folder whose name is not already its slug: rename it to a unique slug,
        write an ``.about.toml`` carrying the old name as the label/description and the
        folder's creation time, and repoint ``[profile] default_role`` /
        ``default_environment`` when they referenced the old name. Idempotent — a folder
        already named as its slug is left untouched, so a second run is a no-op.

        Returns:
            The ``(old, new)`` rename pairs (empty when there was nothing to migrate).
        """
