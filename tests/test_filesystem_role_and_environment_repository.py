# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the two filesystem repositories and the rule store beneath them (real tmp_path)."""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_environment_repository import (
    FilesystemEnvironmentRepositoryAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_role_repository import (
    FilesystemRoleRepositoryAdapter,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_rule_store import FilesystemRuleStore
from generic_ml_wrapper.application.domain.model.environment import Environment
from generic_ml_wrapper.application.domain.model.role import Role

_WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

_RULE = """\
---
name: no-force-push
status: active
---
# no-force-push

**Rule:** Never force-push a shared branch.

**When:** Any push to a branch someone else may have pulled.

**Strength:** hard
"""

_DRAFT = _RULE.replace("status: active", "status: draft").replace("no-force-push", "squash-first")


def _roles(home: Path) -> FilesystemRoleRepositoryAdapter:
    return FilesystemRoleRepositoryAdapter(home, FilesystemRuleStore(), clock=lambda: _WHEN)


def _environments(home: Path) -> FilesystemEnvironmentRepositoryAdapter:
    return FilesystemEnvironmentRepositoryAdapter(home, FilesystemRuleStore(), clock=lambda: _WHEN)


def test_saving_a_role_writes_the_folder_its_dropzone_and_its_sidecar(tmp_path: Path) -> None:
    _roles(tmp_path).save(Role(None, "Code Reviewer", "reads the diff"))
    folder = tmp_path / "profile" / "roles" / "code-reviewer"
    assert folder.is_dir()
    assert (folder / "rules").is_dir()  # the reflexes drop-zone
    about = tomllib.loads((folder / ".about.toml").read_text(encoding="utf-8"))
    assert about["label"] == "Code Reviewer"
    assert about["description"] == "reads the diff"
    assert about["created"] == _WHEN.isoformat()


def test_saving_an_environment_writes_under_environments(tmp_path: Path) -> None:
    _environments(tmp_path).save(Environment(None, "Client Project", "the gig"))
    folder = tmp_path / "environments" / "client-project"
    assert folder.is_dir()
    assert (folder / "rules").is_dir()


def test_exists_reflects_the_folder(tmp_path: Path) -> None:
    repository = _environments(tmp_path)
    assert repository.exists(Environment(None, "Work")) is False
    repository.save(Environment(None, "Work"))
    assert repository.exists(Environment(None, "Work")) is True


def test_find_all_reads_labels_and_sorts_by_code(tmp_path: Path) -> None:
    repository = _environments(tmp_path)
    repository.save(Environment(None, "Work", "the day job"))
    repository.save(Environment(None, "Client Project"))
    found = repository.find_all()
    assert [(e.code, e.label) for e in found] == [
        ("client-project", "Client Project"),
        ("work", "Work"),
    ]


def test_find_all_is_empty_when_the_root_is_missing(tmp_path: Path) -> None:
    assert _roles(tmp_path).find_all() == ()


def test_a_saved_label_is_never_overwritten(tmp_path: Path) -> None:
    repository = _roles(tmp_path)
    repository.save(Role(None, "Code Reviewer"))
    repository.save(Role("code-reviewer", "Something Else"))
    assert repository.find_all()[0].label == "Code Reviewer"


def test_a_missing_sidecar_falls_back_to_the_folder_name(tmp_path: Path) -> None:
    (tmp_path / "profile" / "roles" / "hand-made").mkdir(parents=True)
    found = _roles(tmp_path).find_all()
    assert [(r.code, r.label, r.description) for r in found] == [("hand-made", "hand-made", "")]


def test_a_role_carries_the_rules_inside_its_folder(tmp_path: Path) -> None:
    repository = _roles(tmp_path)
    repository.save(Role(None, "Code Reviewer"))
    rules = tmp_path / "profile" / "roles" / "code-reviewer" / "rules"
    (rules / "no-force-push.rule.md").write_text(_RULE, encoding="utf-8")
    (rules / "squash-first.rule.md").write_text(_DRAFT, encoding="utf-8")
    role = repository.find_all()[0]
    assert [r.code for r in role.rules] == ["no-force-push", "squash-first"]
    assert role.rules[0].rule == "Never force-push a shared branch."
    assert role.rules[0].strength == "hard"
    assert role.rules[0].draft is False
    assert role.rules[1].draft is True
    assert role.draft_count == 1


def test_a_folder_with_no_rules_carries_none(tmp_path: Path) -> None:
    repository = _environments(tmp_path)
    repository.save(Environment(None, "Work"))
    assert repository.find_all()[0].rules == ()


def test_the_rule_store_skips_a_file_it_cannot_read(tmp_path: Path) -> None:
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "good.rule.md").write_text(_RULE, encoding="utf-8")
    (rules / "unreadable.rule.md").write_bytes(b"\xff\xfe\x00bad")
    found = FilesystemRuleStore().find_all(rules)
    assert [r.code for r in found] == ["good"]


def test_the_rule_store_on_a_missing_folder_is_empty(tmp_path: Path) -> None:
    assert FilesystemRuleStore().find_all(tmp_path / "nope") == ()
