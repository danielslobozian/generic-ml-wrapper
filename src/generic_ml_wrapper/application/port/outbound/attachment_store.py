# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the attachment store: the versions gmlw keeps, and their hashes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_wrapper.application.domain.model.attachment import (
        Attachment,
        AttachmentManifest,
        AttachmentVersion,
    )


@dataclass(frozen=True)
class StagedAttachment:
    """An archive unpacked beside the store, not yet part of it.

    Attributes:
        folder: Where it was unpacked.
        manifest_text: The content of its root ``manifest.yaml``, or ``None`` if it has none.
        files: Every file it holds, as ``/``-separated paths relative to ``folder``.
    """

    folder: Path
    manifest_text: str | None
    files: frozenset[str]


class AttachmentStorePort(ABC):
    """Keep every imported version of every attachment, unchanged.

    A version enters only through :meth:`stage` then :meth:`commit`, is never written
    again, and leaves only through :meth:`delete`. Its hash is recorded when it enters, so
    :meth:`is_intact` can tell whether anything touched it since.
    """

    @abstractmethod
    def stage(self, archive: Path) -> StagedAttachment:
        """Unpack an archive beside the store.

        Args:
            archive: The zip to unpack.

        Returns:
            What it unpacked.

        Raises:
            AttachmentError: If the archive cannot be read, or holds an entry that would
                land outside its folder (``..``, an absolute path, a link).
        """

    @abstractmethod
    def discard(self, staged: StagedAttachment) -> None:
        """Remove what :meth:`stage` unpacked; nothing once it has been committed.

        Args:
            staged: The staged attachment.
        """

    @abstractmethod
    def exists(self, name: str, version: AttachmentVersion) -> bool:
        """Whether the store already holds this version.

        Args:
            name: The attachment's name.
            version: The version.

        Returns:
            ``True`` if it is recorded or its folder is there.
        """

    @abstractmethod
    def commit(self, staged: StagedAttachment, manifest: AttachmentManifest) -> Attachment:
        """Move a staged attachment into the store, read-only, and record its hash.

        Args:
            staged: The staged attachment.
            manifest: Its manifest, already checked.

        Returns:
            The stored version.
        """

    @abstractmethod
    def all(self) -> list[Attachment]:
        """Return every stored version, by name then version.

        Returns:
            The stored versions.
        """

    @abstractmethod
    def is_intact(self, attachment: Attachment) -> bool:
        """Whether a stored version is exactly as it was imported.

        Args:
            attachment: The stored version.

        Returns:
            ``True`` if its folder is there and hashes to the recorded hash.
        """

    @abstractmethod
    def delete(self, attachment: Attachment) -> None:
        """Remove a stored version: its folder and its record.

        Args:
            attachment: The stored version.
        """

    @abstractmethod
    def export(self, attachment: Attachment, target: Path) -> None:
        """Write a stored version as a zip, ready to be imported again.

        Args:
            attachment: The stored version.
            target: The zip to write; it must not exist.
        """
