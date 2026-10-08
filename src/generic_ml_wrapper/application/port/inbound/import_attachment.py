# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for importing an attachment from a zip."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.attachment import Attachment


class ImportAttachment(ABC):
    """Add a new version of an attachment to the store."""

    @abstractmethod
    def execute(self, archive: str) -> Attachment:
        """Import an attachment from a zip.

        Args:
            archive: The zip to import.

        Returns:
            The stored version.

        Raises:
            AttachmentError: If the zip cannot be read, holds an unsafe entry, has no or a
                bad manifest, lacks its main file, or that version is already stored.
            IdentifierError: If the manifest's name is not lowercase kebab.
            AttachmentVersionError: If the manifest's version is not ``MAJOR.MINOR.PATCH``.
        """
