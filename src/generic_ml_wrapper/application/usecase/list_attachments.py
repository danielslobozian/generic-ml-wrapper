# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListAttachments use case: every stored version, checked against its hash."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_attachments import (
    AttachmentListing,
    ListAttachments,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.attachment_store import AttachmentStorePort


class ListAttachmentsUseCase(ListAttachments):
    """List the stored versions, each with whether it is still intact."""

    def __init__(self, store: AttachmentStorePort) -> None:
        """Wire the use case to the store.

        Args:
            store: Where attachment versions are kept.
        """
        self._store = store

    def execute(self) -> list[AttachmentListing]:
        """List the stored versions."""
        return [
            AttachmentListing(attachment, self._store.is_intact(attachment))
            for attachment in self._store.all()
        ]
