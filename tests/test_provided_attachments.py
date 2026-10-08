# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the attachments gmlw ships with, and how they reach the store."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.attachment.filesystem_attachment_store import (
    FilesystemAttachmentStore,
)
from generic_ml_wrapper.adapter.outbound.attachment.packaged_attachments import (
    PackagedAttachments,
)
from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.application.domain.service.attachment_manifest import parse_manifest
from generic_ml_wrapper.application.port.outbound.layout_seeder import (
    InitPersist,
    InitSelections,
    LayoutSeederPort,
)
from generic_ml_wrapper.application.usecase.bootstrap import BootstrapUseCase
from generic_ml_wrapper.application.usecase.import_attachment import ImportAttachmentUseCase
from generic_ml_wrapper.application.usecase.install_provided_attachments import (
    InstallProvidedAttachmentsUseCase,
)

if TYPE_CHECKING:
    from pathlib import Path


def _install(
    tmp_path: Path, provided: PackagedAttachments | None = None
) -> tuple[InstallProvidedAttachmentsUseCase, FilesystemAttachmentStore]:
    store = FilesystemAttachmentStore(tmp_path / "attachments", Ledger(tmp_path / "ledger.db"))
    use_case = InstallProvidedAttachmentsUseCase(
        provided or PackagedAttachments(), store, ImportAttachmentUseCase(store)
    )
    return use_case, store


def test_the_shipped_workflow_creator_is_a_valid_attachment() -> None:
    manifests = PackagedAttachments().manifests()

    assert list(manifests) == ["workflow-creator"]
    manifest = parse_manifest(manifests["workflow-creator"])
    assert manifest.name == "workflow-creator"
    assert str(manifest.version) == "1.0.0"
    with (
        PackagedAttachments().zipped("workflow-creator") as archive,
        zipfile.ZipFile(archive) as zipped,
    ):
        names = set(zipped.namelist())
    assert {"manifest.yaml", manifest.main_md_file, "guided.md", "run-conventions.md"} <= names


def test_the_shipped_main_file_points_only_at_files_it_carries() -> None:
    with (
        PackagedAttachments().zipped("workflow-creator") as archive,
        zipfile.ZipFile(archive) as zipped,
    ):
        main = zipped.read("main.md").decode()
        names = set(zipped.namelist())
    for referenced in ("guided.md", "run-conventions.md"):
        assert f"`{referenced}`" in main
        assert referenced in names


def test_provided_attachments_are_imported_once(tmp_path: Path) -> None:
    use_case, store = _install(tmp_path)

    first = use_case.execute()
    second = use_case.execute()

    assert [(a.name, str(a.version)) for a in first] == [("workflow-creator", "1.0.0")]
    assert second == []
    (stored,) = store.all()
    assert store.is_intact(stored)
    assert "## Steps" in store.read_main(stored)


def test_a_new_provided_version_is_added_beside_the_old(tmp_path: Path) -> None:
    package = tmp_path / "package"
    folder = package / "notes"
    folder.mkdir(parents=True)
    (folder / "main.md").write_text("Notes.\n")
    manifest = "name: notes\nversion: {}\nmain_md_file: main.md\n"
    (folder / "manifest.yaml").write_text(manifest.format("1.0.0"))
    use_case, store = _install(tmp_path, PackagedAttachments(package))
    use_case.execute()

    (folder / "manifest.yaml").write_text(manifest.format("1.1.0"))
    use_case.execute()

    assert [str(a.version) for a in store.all()] == ["1.0.0", "1.1.0"]


def test_a_folder_without_a_manifest_is_not_offered(tmp_path: Path) -> None:
    (tmp_path / "package" / "stray").mkdir(parents=True)
    assert PackagedAttachments(tmp_path / "package").manifests() == {}


class _NoSeeding(LayoutSeederPort):
    def ensure(self, default_client: str | None = None, persona: str | None = None) -> None:
        pass

    def initialize(self, selections: InitSelections) -> InitPersist:
        raise NotImplementedError


def test_bootstrap_imports_the_provided_attachments(tmp_path: Path) -> None:
    use_case, store = _install(tmp_path)

    BootstrapUseCase(_NoSeeding(), use_case).execute()

    assert [a.name for a in store.all()] == ["workflow-creator"]


def test_a_broken_provided_attachment_does_not_stop_bootstrap(tmp_path: Path) -> None:
    folder = tmp_path / "package" / "broken"
    folder.mkdir(parents=True)
    (folder / "manifest.yaml").write_text("name: broken\n")
    use_case, store = _install(tmp_path, PackagedAttachments(tmp_path / "package"))

    BootstrapUseCase(_NoSeeding(), use_case).execute()

    assert store.all() == []
