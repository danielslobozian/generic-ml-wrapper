# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem workflow source."""

from pathlib import Path

from generic_ml_wrapper.adapter.outbound.workflow.filesystem_workflow_source import (
    FilesystemWorkflowSource,
)
from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.port.outbound.interceptor import InterceptorPort


def test_seed_copies_packaged_defaults(tmp_path: Path) -> None:
    source = FilesystemWorkflowSource(tmp_path)
    source.seed()
    assert (tmp_path / "create-workflow" / "workflow.md").is_file()
    assert (tmp_path / "_common" / "base.md").is_file()


def test_seed_never_overwrites_user_edits(tmp_path: Path) -> None:
    (tmp_path / "_common").mkdir(parents=True)
    (tmp_path / "_common" / "base.md").write_text("MINE", encoding="utf-8")
    FilesystemWorkflowSource(tmp_path).seed()
    assert (tmp_path / "_common" / "base.md").read_text(encoding="utf-8") == "MINE"


def test_exists_and_create(tmp_path: Path) -> None:
    source = FilesystemWorkflowSource(tmp_path)
    assert source.exists("doc-review") is False
    folder = source.create("doc-review")
    assert Path(folder) == tmp_path / "doc-review"
    assert (tmp_path / "doc-review" / "rules").is_dir()
    assert source.exists("doc-review") is False  # still no workflow.md
    (tmp_path / "doc-review" / "workflow.md").write_text("# doc-review", encoding="utf-8")
    assert source.exists("doc-review") is True


def _add_workflow(root: Path, name: str) -> None:
    (root / name).mkdir(parents=True, exist_ok=True)
    (root / name / "workflow.md").write_text(f"# {name}", encoding="utf-8")


def test_names_lists_runnable_workflows_sorted(tmp_path: Path) -> None:
    source = FilesystemWorkflowSource(tmp_path)
    assert source.names() == []
    _add_workflow(tmp_path, "release")
    _add_workflow(tmp_path, "doc-review")
    assert source.names() == ["doc-review", "release"]


def test_names_hides_base_meta_and_folders_without_workflow_md(tmp_path: Path) -> None:
    source = FilesystemWorkflowSource(tmp_path)
    source.seed()  # brings in _common and create-workflow
    _add_workflow(tmp_path, "doc-review")
    (tmp_path / "half-made").mkdir()  # no workflow.md yet
    assert source.names() == ["doc-review"]


def test_compile_joins_base_and_steps(tmp_path: Path) -> None:
    source = FilesystemWorkflowSource(tmp_path)
    source.seed()
    (tmp_path / "doc-review").mkdir()
    (tmp_path / "doc-review" / "workflow.md").write_text("# doc-review steps", encoding="utf-8")
    compiled = source.compile("doc-review")
    assert "How to run a workflow" in compiled  # from base.md
    assert "# doc-review steps" in compiled


def test_compile_includes_profile_and_rules_in_order(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    profile = tmp_path / "profile"
    rules = tmp_path / "rules"
    for folder in (profile / "me", profile / "company", rules):
        folder.mkdir(parents=True)
    (profile / "me" / "bio.md").write_text("# Me\nI work in French.", encoding="utf-8")
    (profile / "me" / "prefs.md").write_text("I prefer tests first.", encoding="utf-8")
    (profile / "company" / "stack.md").write_text("# Company\nUse hexagonal.", encoding="utf-8")
    (rules / "test-first.rule.md").write_text(
        "---\nname: test-first\nstatus: active\n---\n\n**Rule:** test first.\n\n"
        "**Origin:** learned the hard way.",
        encoding="utf-8",
    )
    _add_workflow(workflows, "doc-review")
    (workflows / "doc-review" / "rules").mkdir()
    (workflows / "doc-review" / "rules" / "scoped.rule.md").write_text(
        "**Rule:** doc-review only.", encoding="utf-8"
    )

    source = FilesystemWorkflowSource(workflows, profile, rules)
    compiled = source.compile("doc-review")

    assert "I work in French." in compiled
    assert "I prefer tests first." in compiled  # second file in profile/me/
    assert "Use hexagonal." in compiled
    assert "**Rule:** test first." in compiled
    assert "**Origin:**" not in compiled  # cleaned
    assert "status: active" not in compiled  # frontmatter cleaned
    assert "**Rule:** doc-review only." in compiled
    # order: profile before the workflow's own steps
    assert compiled.index("I work in French.") < compiled.index("# doc-review")


def test_compile_skips_draft_rules(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "draft.rule.md").write_text(
        "---\nname: d\nstatus: draft\n---\n\n**Rule:** not yet.", encoding="utf-8"
    )
    _add_workflow(workflows, "doc-review")
    compiled = FilesystemWorkflowSource(workflows, None, rules).compile("doc-review")
    assert "not yet" not in compiled


class _Marker(InterceptorPort):
    def __init__(self, mark: str) -> None:
        self._mark = mark

    def intercept(self, text: str, target: str) -> str:
        return f"{self._mark}({text})" if text else text


def test_compile_runs_interceptors_per_target(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "r.rule.md").write_text("**Rule:** be careful.", encoding="utf-8")
    _add_workflow(workflows, "doc-review")
    chain = InterceptorChain([("rules", _Marker("RULES")), ("context", _Marker("CTX"))])

    compiled = FilesystemWorkflowSource(workflows, None, rules, chain).compile("doc-review")

    assert "RULES(**Rule:** be careful.)" in compiled  # rules target ran on the rules blob
    assert compiled.startswith("CTX(")  # context target wrapped the whole compiled blob
