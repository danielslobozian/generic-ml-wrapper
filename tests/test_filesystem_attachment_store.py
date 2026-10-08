# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem attachment store and the import/export/list/delete use cases."""

from __future__ import annotations

import stat
import zipfile
from typing import TYPE_CHECKING

import pytest

from generic_ml_wrapper.adapter.outbound.attachment.filesystem_attachment_store import (
    FilesystemAttachmentStore,
    folder_hash,
)
from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.application.domain.model.attachment import (
    AttachmentError,
    AttachmentVersion,
)
from generic_ml_wrapper.application.usecase.delete_attachment import DeleteAttachmentUseCase
from generic_ml_wrapper.application.usecase.export_attachment import ExportAttachmentUseCase
from generic_ml_wrapper.application.usecase.import_attachment import ImportAttachmentUseCase
from generic_ml_wrapper.application.usecase.list_attachments import ListAttachmentsUseCase

if TYPE_CHECKING:
    from pathlib import Path

_MANIFEST = "name: notes\ndescription: Notes.\nversion: {version}\nmain_md_file: main.md\n"


def _zip(path: Path, files: dict[str, str], *, links: dict[str, str] | None = None) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
        for name, target in (links or {}).items():
            entry = zipfile.ZipInfo(name)
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(entry, target)
    return path


def _attachment(tmp_path: Path, version: str = "1.0.0", name: str = "notes.zip") -> Path:
    return _zip(
        tmp_path / name,
        {
            "manifest.yaml": _MANIFEST.format(version=version),
            "main.md": f"Main {version}. Read more/details.md when needed.\n",
            "more/details.md": "Details.\n",
        },
    )


@pytest.fixture
def store(tmp_path: Path) -> FilesystemAttachmentStore:
    return FilesystemAttachmentStore(tmp_path / "attachments", Ledger(tmp_path / "ledger.db"))


def test_import_stores_the_version_read_only_with_its_hash(
    tmp_path: Path, store: FilesystemAttachmentStore
) -> None:
    attachment = ImportAttachmentUseCase(store).execute(str(_attachment(tmp_path)))

    folder = tmp_path / "attachments" / "notes" / "1.0.0"
    assert (folder / "main.md").read_text() == "Main 1.0.0. Read more/details.md when needed.\n"
    assert (folder / "more" / "details.md").is_file()
    assert attachment.main_md_file == "main.md"
    assert attachment.description == "Notes."
    assert attachment.content_hash == folder_hash(folder)
    assert stat.S_IMODE((folder / "main.md").stat().st_mode) == 0o444
    assert stat.S_IMODE(folder.stat().st_mode) == 0o555
    assert store.all() == [attachment]
    assert store.is_intact(attachment)
    assert list((tmp_path / "attachments" / ".staging").iterdir()) == []


def test_importing_a_stored_version_again_stops(
    tmp_path: Path, store: FilesystemAttachmentStore
) -> None:
    use_case = ImportAttachmentUseCase(store)
    use_case.execute(str(_attachment(tmp_path)))

    with pytest.raises(AttachmentError) as raised:
        use_case.execute(str(_attachment(tmp_path, name="again.zip")))

    assert raised.value.catalogue_key == "error.attachment.exists"
    assert len(store.all()) == 1
    assert list((tmp_path / "attachments" / ".staging").iterdir()) == []


def test_every_version_is_kept_and_listed_by_number(
    tmp_path: Path, store: FilesystemAttachmentStore
) -> None:
    use_case = ImportAttachmentUseCase(store)
    for version in ("2.9.0", "2.10.0", "1.0.0"):
        use_case.execute(str(_attachment(tmp_path, version, f"{version}.zip")))

    listed = ListAttachmentsUseCase(store).execute()

    assert [str(item.attachment.version) for item in listed] == ["1.0.0", "2.9.0", "2.10.0"]
    assert all(item.intact for item in listed)


@pytest.mark.parametrize(
    ("files", "key"),
    [
        ({"main.md": "x"}, "error.attachment.manifest_missing"),
        (
            {"notes/manifest.yaml": _MANIFEST.format(version="1.0.0")},
            "error.attachment.manifest_missing",
        ),
        ({"manifest.yaml": _MANIFEST.format(version="1.0.0")}, "error.attachment.main_missing"),
        (
            {"manifest.yaml": "name: notes\n", "main.md": "x"},
            "error.attachment.manifest_missing_key",
        ),
    ],
)
def test_an_archive_that_is_not_a_valid_attachment_leaves_nothing(
    tmp_path: Path, store: FilesystemAttachmentStore, files: dict[str, str], key: str
) -> None:
    with pytest.raises(AttachmentError) as raised:
        ImportAttachmentUseCase(store).execute(str(_zip(tmp_path / "bad.zip", files)))

    assert raised.value.catalogue_key == key
    assert store.all() == []
    assert not (tmp_path / "attachments" / "notes").exists()
    assert list((tmp_path / "attachments" / ".staging").iterdir()) == []


@pytest.mark.parametrize(
    "entry", ["../escape.md", "/abs.md", "a/../../escape.md", "a\\b.md", "C:x.md"]
)
def test_an_entry_that_would_land_outside_is_refused(
    tmp_path: Path, store: FilesystemAttachmentStore, entry: str
) -> None:
    files = {"manifest.yaml": _MANIFEST.format(version="1.0.0"), "main.md": "x", entry: "x"}

    with pytest.raises(AttachmentError) as raised:
        ImportAttachmentUseCase(store).execute(str(_zip(tmp_path / "bad.zip", files)))

    assert raised.value.catalogue_key == "error.attachment.archive_unsafe"
    assert raised.value.params["entry"] == entry
    assert not (tmp_path / "escape.md").exists()
    assert list((tmp_path / "attachments" / ".staging").iterdir()) == []


def test_a_link_is_refused(tmp_path: Path, store: FilesystemAttachmentStore) -> None:
    archive = _zip(
        tmp_path / "bad.zip",
        {"manifest.yaml": _MANIFEST.format(version="1.0.0"), "main.md": "x"},
        links={"secrets.md": "/etc/passwd"},
    )

    with pytest.raises(AttachmentError) as raised:
        ImportAttachmentUseCase(store).execute(str(archive))

    assert raised.value.catalogue_key == "error.attachment.archive_unsafe"


@pytest.mark.parametrize("content", [None, b"not a zip"])
def test_a_missing_or_unreadable_archive_is_refused(
    tmp_path: Path, store: FilesystemAttachmentStore, content: bytes | None
) -> None:
    archive = tmp_path / "x.zip"
    if content is not None:
        archive.write_bytes(content)

    with pytest.raises(AttachmentError) as raised:
        ImportAttachmentUseCase(store).execute(str(archive))

    assert raised.value.catalogue_key == "error.attachment.archive_unreadable"


def test_a_manifest_that_is_not_utf8_is_refused(
    tmp_path: Path, store: FilesystemAttachmentStore
) -> None:
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("manifest.yaml", b"name: \xff\n")

    with pytest.raises(AttachmentError) as raised:
        ImportAttachmentUseCase(store).execute(str(archive))

    assert raised.value.catalogue_key == "error.attachment.manifest_unreadable"
    assert list((tmp_path / "attachments" / ".staging").iterdir()) == []


@pytest.mark.parametrize("change", ["edit", "add", "remove", "folder", "link"])
def test_any_change_to_a_stored_version_makes_it_invalid(
    tmp_path: Path, store: FilesystemAttachmentStore, change: str
) -> None:
    attachment = ImportAttachmentUseCase(store).execute(str(_attachment(tmp_path)))
    folder = tmp_path / "attachments" / "notes" / "1.0.0"
    folder.chmod(0o755)
    (folder / "more").chmod(0o755)
    if change == "edit":
        (folder / "main.md").chmod(0o644)
        (folder / "main.md").write_text("tampered\n")
    elif change == "add":
        (folder / "extra.md").write_text("x")
    elif change == "remove":
        (folder / "more" / "details.md").unlink()
    elif change == "folder":
        (folder / "empty").mkdir()
    else:
        (folder / "link.md").symlink_to(folder / "main.md")

    assert not store.is_intact(attachment)
    assert [item.intact for item in ListAttachmentsUseCase(store).execute()] == [False]
    with pytest.raises(AttachmentError) as raised:
        ExportAttachmentUseCase(store).execute("notes", None, tmp_path / "out")
    assert raised.value.catalogue_key == "error.attachment.invalid"


def test_a_missing_folder_is_invalid(tmp_path: Path, store: FilesystemAttachmentStore) -> None:
    attachment = ImportAttachmentUseCase(store).execute(str(_attachment(tmp_path)))
    DeleteAttachmentUseCase(store).execute("notes", "1.0.0")

    assert not store.is_intact(attachment)


def test_export_writes_a_zip_that_imports_as_the_same_content(
    tmp_path: Path, store: FilesystemAttachmentStore
) -> None:
    original = ImportAttachmentUseCase(store).execute(str(_attachment(tmp_path)))

    exported = ExportAttachmentUseCase(store).execute("notes", "1.0.0", tmp_path / "out")

    assert exported == tmp_path / "out" / "notes-1.0.0.zip"
    other = FilesystemAttachmentStore(tmp_path / "elsewhere", Ledger(tmp_path / "other.db"))
    again = ImportAttachmentUseCase(other).execute(str(exported))
    assert again == original
    with pytest.raises(AttachmentError) as raised:
        ExportAttachmentUseCase(store).execute("notes", None, tmp_path / "out")
    assert raised.value.catalogue_key == "error.attachment.export_exists"


def test_export_without_a_version_takes_the_highest(
    tmp_path: Path, store: FilesystemAttachmentStore
) -> None:
    use_case = ImportAttachmentUseCase(store)
    for version in ("3.0.0", "2.1.0"):
        use_case.execute(str(_attachment(tmp_path, version, f"{version}.zip")))

    exported = ExportAttachmentUseCase(store).execute("notes", None, tmp_path / "out")

    assert exported.name == "notes-3.0.0.zip"


def test_delete_removes_one_version_and_keeps_the_others(
    tmp_path: Path, store: FilesystemAttachmentStore
) -> None:
    use_case = ImportAttachmentUseCase(store)
    for version in ("1.0.0", "2.0.0"):
        use_case.execute(str(_attachment(tmp_path, version, f"{version}.zip")))

    deleted = DeleteAttachmentUseCase(store).execute("notes", "1.0.0")

    assert deleted.version == AttachmentVersion(1, 0, 0)
    assert [str(a.version) for a in store.all()] == ["2.0.0"]
    assert not (tmp_path / "attachments" / "notes" / "1.0.0").exists()
    DeleteAttachmentUseCase(store).execute("notes", "2.0.0")
    assert not (tmp_path / "attachments" / "notes").exists()


def test_a_deleted_version_can_be_imported_again(
    tmp_path: Path, store: FilesystemAttachmentStore
) -> None:
    use_case = ImportAttachmentUseCase(store)
    use_case.execute(str(_attachment(tmp_path)))
    DeleteAttachmentUseCase(store).execute("notes", "1.0.0")

    use_case.execute(str(_attachment(tmp_path)))

    assert [str(a.version) for a in store.all()] == ["1.0.0"]


def test_deleting_an_unknown_version_is_refused(
    tmp_path: Path, store: FilesystemAttachmentStore
) -> None:
    ImportAttachmentUseCase(store).execute(str(_attachment(tmp_path)))

    with pytest.raises(AttachmentError) as raised:
        DeleteAttachmentUseCase(store).execute("notes", "9.9.9")

    assert raised.value.catalogue_key == "error.attachment.version_not_found"


def test_a_leftover_folder_counts_as_existing(
    tmp_path: Path, store: FilesystemAttachmentStore
) -> None:
    (tmp_path / "attachments" / "notes" / "1.0.0").mkdir(parents=True)

    assert store.exists("notes", AttachmentVersion(1, 0, 0))
    with pytest.raises(AttachmentError) as raised:
        ImportAttachmentUseCase(store).execute(str(_attachment(tmp_path)))
    assert raised.value.catalogue_key == "error.attachment.exists"


def test_folder_hash_depends_on_paths_and_bytes(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    for folder in (first, second):
        folder.mkdir()
    (first / "ab").write_text("c")
    (second / "a").write_text("bc")

    assert folder_hash(first) != folder_hash(second)
