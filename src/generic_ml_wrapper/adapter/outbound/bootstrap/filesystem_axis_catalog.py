# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``AxisCatalogPort``: the role/environment slug-folders under ``~/.gmlw``."""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.about import ABOUT, write_about
from generic_ml_wrapper.application.domain.model.axis import AxisKind, AxisSelection
from generic_ml_wrapper.application.port.outbound.axis_catalog import AxisCatalogPort

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# The two axis roots under the home, mirroring the layout seeder's constants.
_ROOTS = {
    AxisKind.ENVIRONMENT: "environments",
    AxisKind.ROLE: "profile/roles",
}


class FilesystemAxisCatalog(AxisCatalogPort):
    """Read and create the role/environment folders on disk.

    Creation mirrors the init seeder: the slug is the folder name, a role also gets an
    empty ``rules/`` drop-zone, and the human label/description land in the folder's
    ``.about.toml``. A ``clock`` is injected (like the seeder) so tests are deterministic.
    """

    def __init__(self, home: Path, *, clock: Callable[[], datetime] | None = None) -> None:
        """Bind the catalog to a ``~/.gmlw`` home and a clock.

        Args:
            home: The ``~/.gmlw`` root holding ``environments/`` and ``profile/roles/``.
            clock: Returns "now" for the ``.about.toml`` ``created`` stamp; defaults to the
                local wall clock.
        """
        self._home = home
        self._clock = clock or (lambda: datetime.now(UTC).astimezone())

    def _root(self, kind: AxisKind) -> Path:
        return self._home / _ROOTS[kind]

    def list(self, kind: AxisKind) -> list[AxisSelection]:
        """List the existing folders of one axis, sorted by slug (label from ``.about.toml``)."""
        root = self._root(kind)
        if not root.exists():
            return []
        entries: list[AxisSelection] = []
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            label, description = folder.name, ""
            about = folder / ABOUT
            if about.exists():
                try:
                    data = tomllib.loads(about.read_text(encoding="utf-8"))
                except (OSError, tomllib.TOMLDecodeError):
                    data = {}
                label = str(data.get("label", folder.name))
                description = str(data.get("description", ""))
            entries.append(AxisSelection(slug=folder.name, label=label, description=description))
        return entries

    def exists(self, kind: AxisKind, slug: str) -> bool:
        """Whether a folder for ``slug`` already exists in that axis."""
        return (self._root(kind) / slug).is_dir()

    def create(self, kind: AxisKind, slug: str, label: str, description: str, created: str) -> None:
        """Create the slug-folder (plus ``rules/`` for a role) and its ``.about.toml``."""
        folder = self._root(kind) / slug
        if kind is AxisKind.ROLE:
            (folder / "rules").mkdir(parents=True, exist_ok=True)
        else:
            folder.mkdir(parents=True, exist_ok=True)
        write_about(folder, label, description, created)
