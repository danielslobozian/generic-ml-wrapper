# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ExportAttachment use case: write a stored version back as a zip."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.attachment import (
    AttachmentError,
    AttachmentVersion,
    find,
)
from generic_ml_wrapper.application.port.inbound.export_attachment import ExportAttachment

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_wrapper.application.port.outbound.attachment_store import AttachmentStorePort


class ExportAttachmentUseCase(ExportAttachment):
    """Export a version, only while it is exactly as imported."""

    def __init__(self, store: AttachmentStorePort) -> None:
        """Wire the use case to the store.

        Args:
            store: Where attachment versions are kept.
        """
        self._store = store

    def execute(self, name: str, version: str | None, folder: Path) -> Path:
        """Export one version."""
        wanted = None if version is None else AttachmentVersion.parse(version)
        attachment = find(self._store.all(), name, wanted)
        if not self._store.is_intact(attachment):
            raise AttachmentError(
                "error.attachment.invalid", name=name, version=str(attachment.version)
            )
        target = folder / f"{attachment.name}-{attachment.version}.zip"
        if target.exists():
            raise AttachmentError("error.attachment.export_exists", path=str(target))
        self._store.export(attachment, target)
        return target
