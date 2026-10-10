# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the one-time import of an older gmlw's workflows as attachments."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.attachment.filesystem_attachment_store import (
    FilesystemAttachmentStore,
)
from generic_ml_wrapper.adapter.outbound.attachment.filesystem_legacy_workflows import (
    FilesystemLegacyWorkflows,
)
from generic_ml_wrapper.adapter.outbound.store.ledger import Ledger
from generic_ml_wrapper.application.usecase.import_attachment import ImportAttachmentUseCase
from generic_ml_wrapper.application.usecase.migrate_legacy_workflows import (
    MigrateLegacyWorkflowsUseCase,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _old_home(home: Path) -> Path:
    """An old workflows folder, with what real ones accumulate."""
    root = home / "workflows"
    _write(root / "_common" / "base.md", "# How to run a workflow\nOne step at a time.")
    _write(root / "create-workflow" / "workflow.md", "# create-workflow")
    review = root / "doc-review"
    _write(review / "workflow.md", "# doc-review\n1. Read references/checklist.md")
    _write(review / ".about.toml", "label = 'Doc Review'\ndescription = 'Review \"the\" docs #1'\n")
    _write(review / "references" / "checklist.md", "- spelling")
    _write(review / "scripts" / "lint.py", "print('ok')")
    _write(review / "scripts" / "__pycache__" / "lint.cpython-314.pyc")
    _write(review / "scripts" / "lint.py.bak-2026-09-01")
    _write(review / "workflow.md.bak-2026-09-07")
    _write(review / "draft.md")
    _write(review / "parking-lot.md")
    _write(review / ".claude" / "settings.json", "{}")
    _write(root / "Bad Name" / "workflow.md")
    (root / "not-a-workflow").mkdir()
    return root


def _migration(home: Path) -> tuple[MigrateLegacyWorkflowsUseCase, FilesystemAttachmentStore]:
    store = FilesystemAttachmentStore(home / "attachments", Ledger(home / "ledger.db"))
    legacy = FilesystemLegacyWorkflows(home / "workflows", home / "state", home / "config.toml")
    return MigrateLegacyWorkflowsUseCase(legacy, ImportAttachmentUseCase(store)), store


def test_each_workflow_becomes_an_attachment_at_1_0_0(tmp_path: Path) -> None:
    _old_home(tmp_path)
    migration, store = _migration(tmp_path)

    report = migration.execute()

    assert report.imported == ["doc-review@1.0.0"]
    assert report.skipped == [("Bad Name", "error.identifier.attachment_name")]
    assert report.folder == str(tmp_path / "workflows")
    (stored,) = store.all()
    assert stored.main_md_file == "workflow.md"
    assert stored.description == "Review 'the' docs #1"
    folder = store.folder(stored)
    files = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    assert files == ["manifest.yaml", "references/checklist.md", "scripts/lint.py", "workflow.md"]


def test_the_old_shared_base_leads_the_main_file(tmp_path: Path) -> None:
    _old_home(tmp_path)
    migration, store = _migration(tmp_path)
    migration.execute()

    main = store.read_main(store.all()[0])

    assert main.startswith("# How to run a workflow\nOne step at a time.\n\n\n# doc-review")


def test_the_old_folder_is_left_exactly_as_it_was(tmp_path: Path) -> None:
    root = _old_home(tmp_path)
    before = sorted(
        (p.relative_to(root).as_posix(), p.read_bytes()) for p in root.rglob("*") if p.is_file()
    )
    migration, _ = _migration(tmp_path)

    migration.execute()

    after = sorted(
        (p.relative_to(root).as_posix(), p.read_bytes()) for p in root.rglob("*") if p.is_file()
    )
    assert after == before


def test_it_runs_once(tmp_path: Path) -> None:
    _old_home(tmp_path)
    migration, store = _migration(tmp_path)
    migration.execute()
    store.delete(store.all()[0])  # the user deletes it: it must not come back

    again = migration.execute()

    assert not again.did_anything
    assert store.all() == []


def test_a_home_without_old_workflows_reports_nothing(tmp_path: Path) -> None:
    migration, _ = _migration(tmp_path)

    report = migration.execute()

    assert not report.did_anything
    assert report.folder == ""


def test_old_config_keys_are_renamed_and_the_rest_kept(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        "# mine\n"
        "[startup.workflow.context]\n"
        "company = { activated = false }  # keep this\n"
        "base = { compression = false }\n"
        "steps = { compression = true }\n\n"
        "[startup.authoring.context]\n"
        "persona = { activated = true }\n\n"
        "[[interceptors]]\n"
        'target = "workflow"\n'
        'spec = "x:Y"\n',
        encoding="utf-8",
    )
    migration, _ = _migration(tmp_path)

    report = migration.execute()

    text = config.read_text(encoding="utf-8")
    assert report.config_rewritten is True
    assert "# mine" in text
    assert "[startup.attachment.context]" in text
    assert "company = { activated = false }  # keep this" in text
    assert "base" not in text
    assert "steps" not in text
    assert "authoring" not in text
    assert 'target = "attachment"' in text


def test_an_existing_attachment_mode_is_not_overwritten(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        "[startup.attachment.context]\ncompany = { activated = true }\n\n"
        "[startup.workflow.context]\ncompany = { activated = false }\n",
        encoding="utf-8",
    )
    migration, _ = _migration(tmp_path)

    migration.execute()

    text = config.read_text(encoding="utf-8")
    assert "company = { activated = true }" in text
    assert "activated = false" not in text


def test_a_config_without_old_keys_is_not_rewritten(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    original = '[client]\ndefault = "claude"\n'
    config.write_text(original, encoding="utf-8")
    migration, _ = _migration(tmp_path)

    assert migration.execute().config_rewritten is False
    assert config.read_text(encoding="utf-8") == original


def test_an_unreadable_config_is_left_alone(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text("[broken\n", encoding="utf-8")
    migration, _ = _migration(tmp_path)

    assert migration.execute().config_rewritten is False
    assert config.read_text(encoding="utf-8") == "[broken\n"
