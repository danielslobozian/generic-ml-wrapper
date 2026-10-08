# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for exporting a stored attachment version as a zip."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class ExportAttachment(ABC):
    """Write a stored version back as a zip, ready to be imported elsewhere."""

    @abstractmethod
    def execute(self, name: str, version: str | None, folder: Path) -> Path:
        """Export one version.

        Args:
            name: The attachment's name.
            version: The version, or ``None`` for the highest.
            folder: Where to write ``<name>-<version>.zip``.

        Returns:
            The written zip.

        Raises:
            AttachmentError: If that version is not stored, was changed since its import,
                or the zip already exists.
        """
