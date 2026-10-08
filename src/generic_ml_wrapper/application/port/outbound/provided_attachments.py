# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the attachments gmlw ships with."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from pathlib import Path


class ProvidedAttachmentsPort(ABC):
    """The attachments packaged with gmlw, each offered as the zip a user would import."""

    @abstractmethod
    def manifests(self) -> dict[str, str]:
        """Return each provided attachment's manifest text, by its folder in the package.

        Returns:
            The manifest texts, keyed by the attachment's package folder.
        """

    @abstractmethod
    def zipped(self, folder: str) -> AbstractContextManager[Path]:
        """Zip one provided attachment, for as long as the context lasts.

        Args:
            folder: The attachment's package folder, a key of :meth:`manifests`.

        Returns:
            A context yielding the zip's path; the zip is removed when it exits.
        """
