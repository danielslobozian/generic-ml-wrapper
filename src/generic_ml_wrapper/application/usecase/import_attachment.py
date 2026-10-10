# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ImportAttachment use case: unpack, check, then store a new version.

Everything is checked on the staged copy, before the store changes: a zip that is not a
valid attachment, or a version that is already stored, leaves the store as it was.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.attachment import AttachmentError
from generic_ml_wrapper.application.domain.service.attachment_manifest import (
    MANIFEST,
    parse_manifest,
)
from generic_ml_wrapper.application.port.inbound.import_attachment import ImportAttachment

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.attachment import Attachment
    from generic_ml_wrapper.application.port.outbound.attachment_store import AttachmentStorePort


class ImportAttachmentUseCase(ImportAttachment):
    """Add a version to the store, refusing one that is already there."""

    def __init__(self, store: AttachmentStorePort) -> None:
        """Wire the use case to the store.

        Args:
            store: Where attachment versions are kept.
        """
        self._store = store

    def execute(self, archive: str) -> Attachment:
        """Import an attachment from a zip."""
        staged = self._store.stage(Path(archive))
        try:
            if staged.manifest_text is None:
                raise AttachmentError(
                    "error.attachment.manifest_missing", archive=archive, manifest=MANIFEST
                )
            manifest = parse_manifest(staged.manifest_text)
            if manifest.main_md_file not in staged.files:
                raise AttachmentError("error.attachment.main_missing", file=manifest.main_md_file)
            if self._store.exists(manifest.name, manifest.version):
                raise AttachmentError(
                    "error.attachment.exists", name=manifest.name, version=str(manifest.version)
                )
            return self._store.commit(staged, manifest)
        finally:
            self._store.discard(staged)
