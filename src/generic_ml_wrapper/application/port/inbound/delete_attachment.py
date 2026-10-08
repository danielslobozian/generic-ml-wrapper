# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for deleting one stored attachment version."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.attachment import Attachment


class DeleteAttachment(ABC):
    """Remove one version from the store."""

    @abstractmethod
    def execute(self, name: str, version: str) -> Attachment:
        """Delete one version.

        Args:
            name: The attachment's name.
            version: The version.

        Returns:
            The version that was deleted.

        Raises:
            AttachmentError: If that version is not stored.
            AttachmentVersionError: If ``version`` is not ``MAJOR.MINOR.PATCH``.
        """
