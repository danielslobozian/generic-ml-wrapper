# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the role/environment catalog: the slug-folders on disk."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.axis import AxisKind, AxisSelection


class AxisCatalogPort(ABC):
    """Read and create the role/environment slug-folders (each with its ``.about.toml``).

    The folder name is the slug (the id and the ``[profile]`` config value); the sidecar
    carries the human label and description. This port is the single owner of that layout,
    so listing and creation share one place rather than each caller re-scanning by hand.
    """

    @abstractmethod
    def list(self, kind: AxisKind) -> list[AxisSelection]:
        """List the existing folders of one axis.

        Args:
            kind: Which axis to list (role or environment).

        Returns:
            One :class:`AxisSelection` per folder (slug + label + description read from its
            ``.about.toml``, falling back to the slug when absent), sorted by slug.
        """

    @abstractmethod
    def exists(self, kind: AxisKind, slug: str) -> bool:
        """Whether a folder for ``slug`` already exists in that axis.

        Args:
            kind: Which axis to check.
            slug: The kebab-case id (folder name).

        Returns:
            ``True`` if the folder is present.
        """

    @abstractmethod
    def create(self, kind: AxisKind, slug: str, label: str, description: str, created: str) -> None:
        """Create a new slug-folder for an axis, with its ``.about.toml``.

        Creates the folder (and, for a role, an empty ``rules/`` drop-zone) and writes the
        sidecar. Idempotent on the directory; the sidecar is written missing-only.

        Args:
            kind: Which axis the folder belongs to.
            slug: The kebab-case id (folder name).
            label: The human name the slug came from.
            description: A fuller line saved alongside the label.
            created: An ISO-8601 timestamp for when the folder was created.
        """
