# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Packaged ``ProvidedAttachmentsPort``: the attachments under ``resources/attachments``."""

from __future__ import annotations

import tempfile
import zipfile
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.service.attachment_manifest import MANIFEST
from generic_ml_wrapper.application.port.outbound.provided_attachments import (
    ProvidedAttachmentsPort,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator
    from importlib.resources.abc import Traversable


class PackagedAttachments(ProvidedAttachmentsPort):
    """Offer each folder under the package's ``resources/attachments`` as a zip."""

    def __init__(self, root: Traversable | None = None) -> None:
        """Bind to the folder holding the provided attachments.

        Args:
            root: That folder; defaults to the package's ``resources/attachments``.
        """
        self._root = root or resources.files("generic_ml_wrapper").joinpath(
            "resources", "attachments"
        )

    def manifests(self) -> dict[str, str]:
        """Each folder's ``manifest.yaml``, skipping a folder without one."""
        found: dict[str, str] = {}
        for folder in sorted(self._root.iterdir(), key=lambda entry: entry.name):
            manifest = folder.joinpath(MANIFEST)
            if folder.is_dir() and manifest.is_file():
                found[folder.name] = manifest.read_text(encoding="utf-8")
        return found

    @contextmanager
    def zipped(self, folder: str) -> Generator[Path]:
        """Zip the folder's files, paths relative to it, into a temporary zip."""
        with tempfile.TemporaryDirectory(prefix="gmlw-provided-") as scratch:
            target = Path(scratch) / f"{folder}.zip"
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                for relative, entry in sorted(_files(self._root.joinpath(folder))):
                    archive.writestr(relative, entry.read_bytes())
            yield target


def _files(folder: Traversable, prefix: str = "") -> Iterator[tuple[str, Traversable]]:
    for entry in folder.iterdir():
        relative = f"{prefix}{entry.name}"
        if entry.is_dir():
            if entry.name != "__pycache__":
                yield from _files(entry, f"{relative}/")
        else:
            yield relative, entry
