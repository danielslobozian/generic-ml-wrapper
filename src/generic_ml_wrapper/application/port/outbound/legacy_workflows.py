# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the old ``workflows/`` folder, read once to become attachments."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from pathlib import Path


class LegacyWorkflowsPort(ABC):
    """The folders an older gmlw kept workflows in, offered as attachment zips.

    Read only: nothing under the old folder is moved, changed or deleted.
    """

    @abstractmethod
    def migrated(self) -> bool:
        """Whether the migration already ran on this home.

        Returns:
            ``True`` once :meth:`mark_migrated` has been called.
        """

    @abstractmethod
    def mark_migrated(self) -> None:
        """Record that the migration ran, so it never runs again."""

    @abstractmethod
    def folder(self) -> Path | None:
        """The old folder, or ``None`` when this home has none.

        Returns:
            Its path, when it exists.
        """

    @abstractmethod
    def names(self) -> list[str]:
        """The folders that held a workflow, sorted; gmlw's own are left out.

        Returns:
            Their names.
        """

    @abstractmethod
    def zipped(self, name: str) -> AbstractContextManager[Path]:
        """One folder as an attachment zip at ``1.0.0``, for as long as the context lasts.

        Args:
            name: A folder from :meth:`names`.

        Returns:
            A context yielding the zip's path; the zip is removed when it exits.
        """

    @abstractmethod
    def rewrite_config(self) -> bool:
        """Rename the old keys in ``config.toml``, keeping everything else as written.

        Returns:
            ``True`` if the file changed.
        """
