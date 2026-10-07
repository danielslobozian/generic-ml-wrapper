# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem rule catalogue behind the TUI's Rules browser."""

from __future__ import annotations

from pathlib import Path

from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_axis_catalog import (
    FilesystemAxisCatalog,
)
from generic_ml_wrapper.adapter.outbound.bootstrap.filesystem_rule_catalog import (
    FilesystemRuleCatalog,
)
from generic_ml_wrapper.application.domain.model.rule_catalog import RuleAxis


def _catalog(home: Path) -> FilesystemRuleCatalog:
    return FilesystemRuleCatalog(home, FilesystemAxisCatalog(home))


def _write_rule(folder: Path, slug: str, body: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{slug}.rule.md").write_text(body, encoding="utf-8")


def test_no_rules_yields_no_groups(tmp_path: Path) -> None:
    (tmp_path / "environments" / "work").mkdir(parents=True)
    (tmp_path / "profile" / "roles" / "engineer").mkdir(parents=True)
    # Both axes exist but neither holds a rule: nothing to walk into.
    assert _catalog(tmp_path).groups() == ()


def test_only_populated_groups_are_listed(tmp_path: Path) -> None:
    (tmp_path / "environments" / "work" / "rules").mkdir(parents=True)  # empty
    _write_rule(
        tmp_path / "profile" / "roles" / "software-engineer" / "rules",
        "no-transactional",
        "---\nname: no-transactional\nstatus: active\n---\n\n"
        "**Rule:** No @Transactional in a use case.\n\n**When:** Reviewing hexagonal Java.",
    )
    groups = _catalog(tmp_path).groups()
    assert len(groups) == 1
    assert groups[0].axis is RuleAxis.ROLE
    assert groups[0].slug == "software-engineer"
    assert groups[0].rules[0].rule == "No @Transactional in a use case."
    assert groups[0].rules[0].when == "Reviewing hexagonal Java."


def test_environments_are_listed_before_roles(tmp_path: Path) -> None:
    _write_rule(
        tmp_path / "environments" / "work" / "rules", "lint", "**Rule:** Use the house config."
    )
    _write_rule(
        tmp_path / "profile" / "roles" / "engineer" / "rules", "tdd", "**Rule:** Tests first."
    )
    axes = [group.axis for group in _catalog(tmp_path).groups()]
    assert axes == [RuleAxis.ENVIRONMENT, RuleAxis.ROLE]


def test_drafts_are_listed_and_flagged(tmp_path: Path) -> None:
    # A draft is injected into no session, so the browser must show it *and* mark it —
    # hiding it would make "what is actually live" unanswerable.
    rules = tmp_path / "profile" / "roles" / "engineer" / "rules"
    _write_rule(rules, "live", "---\nname: live\nstatus: active\n---\n\n**Rule:** Shipped.")
    _write_rule(rules, "pending", "---\nname: pending\nstatus: draft\n---\n\n**Rule:** Proposed.")
    group = _catalog(tmp_path).groups()[0]
    assert [(r.slug, r.draft) for r in group.rules] == [("live", False), ("pending", True)]
    assert group.draft_count == 1


def test_the_group_label_comes_from_about_toml(tmp_path: Path) -> None:
    role = tmp_path / "profile" / "roles" / "software-engineer"
    _write_rule(role / "rules", "tdd", "**Rule:** Tests first.")
    (role / ".about.toml").write_text('label = "Software engineer"\n', encoding="utf-8")
    assert _catalog(tmp_path).groups()[0].label == "Software engineer"


def test_a_non_rule_file_is_ignored(tmp_path: Path) -> None:
    rules = tmp_path / "environments" / "work" / "rules"
    rules.mkdir(parents=True)
    (rules / "notes.md").write_text("**Rule:** not a rule file.", encoding="utf-8")
    assert _catalog(tmp_path).groups() == ()
