# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing the stored attachment versions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.attachment import Attachment


@dataclass(frozen=True)
class AttachmentListing:
    """One stored version, and whether it is still as imported.

    Attributes:
        attachment: The stored version.
        intact: ``False`` if its folder changed since its import; it cannot be attached.
    """

    attachment: Attachment
    intact: bool


class ListAttachments(ABC):
    """List every stored version."""

    @abstractmethod
    def execute(self) -> list[AttachmentListing]:
        """List the stored versions.

        Returns:
            Every stored version, by name then version.
        """
