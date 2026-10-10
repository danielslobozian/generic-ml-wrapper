# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Bring an older gmlw's workflows in as attachments, once.

Each folder goes through the ordinary import, as ``<name>@1.0.0``. Nothing under the old
folder is touched, so the user's own copy stays exactly as it was until they delete it.
A folder that cannot be imported is reported, not fatal: the rest still come in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.migration import LegacyMigrationReport
from generic_ml_wrapper.common.errors import DomainError

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.inbound.import_attachment import ImportAttachment
    from generic_ml_wrapper.application.port.outbound.legacy_workflows import LegacyWorkflowsPort


class MigrateLegacyWorkflowsUseCase:
    """Import each old workflow folder once, and rename the old config keys."""

    def __init__(self, legacy: LegacyWorkflowsPort, importer: ImportAttachment) -> None:
        """Wire the use case to the old folder and the import.

        Args:
            legacy: The old workflows, offered as zips.
            importer: The import every attachment goes through.
        """
        self._legacy = legacy
        self._importer = importer

    def execute(self) -> LegacyMigrationReport:
        """Run the migration, unless it already ran.

        Returns:
            What it imported and skipped; an empty report when there was nothing to do.
        """
        if self._legacy.migrated():
            return LegacyMigrationReport()
        imported: list[str] = []
        skipped: list[tuple[str, str]] = []
        for name in self._legacy.names():
            try:
                with self._legacy.zipped(name) as archive:
                    attachment = self._importer.execute(str(archive))
            except DomainError as error:
                skipped.append((name, error.catalogue_key))
                continue
            imported.append(f"{attachment.name}@{attachment.version}")
        rewritten = self._legacy.rewrite_config()
        folder = self._legacy.folder()
        self._legacy.mark_migrated()
        return LegacyMigrationReport(
            imported=imported,
            skipped=skipped,
            config_rewritten=rewritten,
            folder="" if folder is None else str(folder),
        )
