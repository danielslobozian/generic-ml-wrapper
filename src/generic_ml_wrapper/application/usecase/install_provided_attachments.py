# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Bring the attachments gmlw ships with into the store, through the ordinary import.

gmlw has no other path for its own attachments: each is zipped and imported exactly as a
user's would be. A version already stored is skipped, so this runs at every start for
the price of reading a manifest, and a gmlw upgrade that carries a new version adds it
beside the old ones.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.service.attachment_manifest import parse_manifest

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.attachment import Attachment
    from generic_ml_wrapper.application.port.inbound.import_attachment import ImportAttachment
    from generic_ml_wrapper.application.port.outbound.attachment_store import AttachmentStorePort
    from generic_ml_wrapper.application.port.outbound.provided_attachments import (
        ProvidedAttachmentsPort,
    )


class InstallProvidedAttachmentsUseCase:
    """Import each provided attachment version the store does not have yet."""

    def __init__(
        self,
        provided: ProvidedAttachmentsPort,
        store: AttachmentStorePort,
        importer: ImportAttachment,
    ) -> None:
        """Wire the use case to the provided attachments, the store, and the import.

        Args:
            provided: The attachments gmlw ships with.
            store: Where attachment versions are kept.
            importer: The import every attachment goes through.
        """
        self._provided = provided
        self._store = store
        self._importer = importer

    def execute(self) -> list[Attachment]:
        """Import what is missing.

        Returns:
            The versions imported now (empty when all were already stored).
        """
        imported: list[Attachment] = []
        for folder, text in self._provided.manifests().items():
            manifest = parse_manifest(text)
            if self._store.exists(manifest.name, manifest.version):
                continue
            with self._provided.zipped(folder) as archive:
                imported.append(self._importer.execute(str(archive)))
        return imported
