# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The DeleteAttachment use case: remove one stored version.

An invalid version can be deleted too: deleting it and importing it again is how it is
repaired.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.attachment import AttachmentVersion, find
from generic_ml_wrapper.application.port.inbound.delete_attachment import DeleteAttachment

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.attachment import Attachment
    from generic_ml_wrapper.application.port.outbound.attachment_store import AttachmentStorePort


class DeleteAttachmentUseCase(DeleteAttachment):
    """Delete one version from the store."""

    def __init__(self, store: AttachmentStorePort) -> None:
        """Wire the use case to the store.

        Args:
            store: Where attachment versions are kept.
        """
        self._store = store

    def execute(self, name: str, version: str) -> Attachment:
        """Delete one version."""
        attachment = find(self._store.all(), name, AttachmentVersion.parse(version))
        self._store.delete(attachment)
        return attachment
