# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``AttachmentStorePort``: versions under ``~/.gmlw/attachments``, hashes in the ledger.

A version lives at ``<root>/<name>/<version>/``, read-only. Archives are unpacked into
``<root>/.staging/`` first -- a name cannot start with ``.``, so it never collides with
one -- on the same filesystem, so committing is a rename.

Unpacking refuses an entry that would land outside its folder, rather than rewriting it
the way ``zipfile.extractall`` does: an attachment that carries ``../x`` is not what its
author thinks it is, and storing a silently different one would make its hash certify
the wrong thing.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.attachment import (
    Attachment,
    AttachmentError,
    AttachmentVersion,
)
from generic_ml_wrapper.application.domain.model.identifiers import AttachmentName
from generic_ml_wrapper.application.domain.service.attachment_manifest import MANIFEST
from generic_ml_wrapper.application.port.outbound.attachment_store import (
    AttachmentStorePort,
    StagedAttachment,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
    from generic_ml_wrapper.application.domain.model.attachment import AttachmentManifest

_STAGING = ".staging"
_READ_ONLY_FILE = 0o444
_READ_ONLY_DIR = 0o555
_WRITABLE_FILE = 0o644
_WRITABLE_DIR = 0o755
_COPY_CHUNK = 1 << 20


class FilesystemAttachmentStore(AttachmentStorePort):
    """Keep attachment versions as read-only folders, and their hashes in the ledger."""

    def __init__(self, root: Path, ledger: Ledger) -> None:
        """Bind the store to its root folder and the ledger.

        Args:
            root: The store, ``~/.gmlw/attachments``.
            ledger: Where each version's hash is recorded.
        """
        self._root = root
        self._ledger = ledger

    def stage(self, archive: Path) -> StagedAttachment:
        """Unpack an archive into a fresh folder under ``.staging``."""
        staging = self._root / _STAGING
        staging.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(dir=staging))
        try:
            files = _unpack(archive, folder)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        manifest = folder / MANIFEST
        try:
            text = manifest.read_text(encoding="utf-8") if manifest.is_file() else None
        except (UnicodeDecodeError, OSError) as error:
            shutil.rmtree(folder, ignore_errors=True)
            raise AttachmentError(
                "error.attachment.manifest_unreadable", archive=str(archive)
            ) from error
        return StagedAttachment(folder=folder, manifest_text=text, files=files)

    def discard(self, staged: StagedAttachment) -> None:
        """Remove the staged folder, if it is still there."""
        shutil.rmtree(staged.folder, ignore_errors=True)

    def exists(self, name: str, version: AttachmentVersion) -> bool:
        """Whether this version is recorded, or its folder is there."""
        with self._ledger.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM attachments WHERE name = ? AND version = ?", (name, str(version))
            ).fetchone()
        return row is not None or self._folder(name, version).exists()

    def commit(self, staged: StagedAttachment, manifest: AttachmentManifest) -> Attachment:
        """Rename the staged folder into place, make it read-only, record its hash."""
        target = self._folder(manifest.name, manifest.version)
        target.parent.mkdir(parents=True, exist_ok=True)
        staged.folder.rename(target)
        try:
            _set_mode(target, file_mode=_READ_ONLY_FILE, dir_mode=_READ_ONLY_DIR)
            attachment = Attachment(
                name=manifest.name,
                version=manifest.version,
                description=manifest.description,
                main_md_file=manifest.main_md_file,
                content_hash=folder_hash(target),
            )
            with self._ledger.connect() as connection:
                connection.execute(
                    "INSERT INTO attachments "
                    "(name, version, description, main_md_file, content_hash) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        attachment.name,
                        str(attachment.version),
                        attachment.description,
                        attachment.main_md_file,
                        attachment.content_hash,
                    ),
                )
        except BaseException:
            _remove(target)
            raise
        return attachment

    def all(self) -> list[Attachment]:
        """Every recorded version, by name then version (as numbers)."""
        with self._ledger.connect() as connection:
            rows = connection.execute(
                "SELECT name, version, description, main_md_file, content_hash FROM attachments"
            ).fetchall()
        found = [
            Attachment(
                name=AttachmentName(row["name"]),
                version=AttachmentVersion.parse(row["version"]),
                description=row["description"],
                main_md_file=row["main_md_file"],
                content_hash=row["content_hash"],
            )
            for row in rows
        ]
        return sorted(found, key=lambda attachment: (attachment.name, attachment.version))

    def is_intact(self, attachment: Attachment) -> bool:
        """Whether the folder is there and hashes to the recorded hash."""
        folder = self._folder(attachment.name, attachment.version)
        return folder.is_dir() and folder_hash(folder) == attachment.content_hash

    def delete(self, attachment: Attachment) -> None:
        """Remove the folder (and the name's folder once empty), then the record."""
        folder = self._folder(attachment.name, attachment.version)
        _remove(folder)
        with contextlib.suppress(OSError):  # other versions remain, or it was never there
            folder.parent.rmdir()
        with self._ledger.connect() as connection:
            connection.execute(
                "DELETE FROM attachments WHERE name = ? AND version = ?",
                (attachment.name, str(attachment.version)),
            )

    def export(self, attachment: Attachment, target: Path) -> None:
        """Zip the version's files, paths relative to its folder."""
        folder = self._folder(attachment.name, attachment.version)
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(folder).as_posix())

    def _folder(self, name: str, version: AttachmentVersion) -> Path:
        return self._root / name / str(version)


def folder_hash(folder: Path) -> str:
    """The SHA-256 of a folder: every entry's relative path and, for a file, its bytes.

    Entries are taken in sorted path order, each tagged with its kind and its length, so
    no two different folders produce the same stream. A folder or a link added inside
    changes the hash as surely as an edited file.

    Args:
        folder: The folder to hash.

    Returns:
        The hex digest.
    """
    digest = hashlib.sha256()
    for path in sorted(folder.rglob("*"), key=lambda entry: entry.relative_to(folder).as_posix()):
        relative = path.relative_to(folder).as_posix().encode()
        if path.is_symlink():
            digest.update(b"L" + relative + b"\0" + str(path.readlink()).encode() + b"\0")
        elif path.is_dir():
            digest.update(b"D" + relative + b"\0")
        else:
            content = path.read_bytes()
            digest.update(b"F" + relative + b"\0" + len(content).to_bytes(8, "big") + content)
    return digest.hexdigest()


def _unpack(archive: Path, folder: Path) -> frozenset[str]:
    """Extract every entry under ``folder``, refusing one that would land elsewhere."""
    try:
        with zipfile.ZipFile(archive) as zipped:
            entries = zipped.infolist()
            for entry in entries:
                if not _safe(entry):
                    raise AttachmentError(
                        "error.attachment.archive_unsafe",
                        archive=str(archive),
                        entry=entry.filename,
                    )
            files: set[str] = set()
            for entry in entries:
                landing = folder / entry.filename
                if entry.is_dir():
                    landing.mkdir(parents=True, exist_ok=True)
                    continue
                landing.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(entry) as source, landing.open("xb") as sink:
                    shutil.copyfileobj(source, sink, _COPY_CHUNK)
                files.add(entry.filename)
    except (zipfile.BadZipFile, OSError) as error:
        raise AttachmentError(
            "error.attachment.archive_unreadable", archive=str(archive)
        ) from error
    return frozenset(files)


def _safe(entry: zipfile.ZipInfo) -> bool:
    """Whether an entry lands inside the folder: relative, no ``..``, not a link."""
    name = entry.filename
    if not name or name.startswith("/") or "\\" in name or (len(name) > 1 and name[1] == ":"):
        return False
    parts = name.rstrip("/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    return not stat.S_ISLNK(entry.external_attr >> 16)


def _set_mode(folder: Path, *, file_mode: int, dir_mode: int) -> None:
    """Set every file's and folder's mode, bottom up so a folder is changed last.

    Links are skipped: changing a link's mode changes its target's, which may be anywhere.
    """
    for current, dirs, files in os.walk(folder, topdown=False):
        for name in files:
            _chmod(Path(current, name), file_mode)
        for name in dirs:
            _chmod(Path(current, name), dir_mode)
    _chmod(folder, dir_mode)


def _chmod(path: Path, mode: int) -> None:
    if not path.is_symlink():
        path.chmod(mode)


def _remove(folder: Path) -> None:
    """Remove a folder this store made read-only."""
    if not folder.exists():
        return
    _chmod(folder, _WRITABLE_DIR)
    for current, dirs, files in os.walk(folder):
        for name in dirs:
            _chmod(Path(current, name), _WRITABLE_DIR)
        for name in files:
            _chmod(Path(current, name), _WRITABLE_FILE)
    shutil.rmtree(folder)
