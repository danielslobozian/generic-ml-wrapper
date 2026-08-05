# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem workflow source."""

import json
from pathlib import Path

from generic_ml_wrapper.adapter.outbound.config import toml_config_reader as config
from generic_ml_wrapper.adapter.outbound.workflow.filesystem_workflow_source import (
    FilesystemWorkflowSourceAdapter,
)
from generic_ml_wrapper.application.domain.model.context_source import CompileMode
from generic_ml_wrapper.application.domain.model.draft import DraftMarker
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.application.domain.model.workflow import Workflow
from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.port.outbound.context_compressor import ContextCompressorPort
from generic_ml_wrapper.application.port.outbound.interceptor import InterceptorPort
from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort


def test_seed_copies_packaged_defaults(tmp_path: Path) -> None:
    source = FilesystemWorkflowSourceAdapter(tmp_path)
    source.seed()
    assert (tmp_path / "create-workflow" / "workflow.md").is_file()
    assert (tmp_path / "_common" / "base.md").is_file()


def test_seed_never_overwrites_user_edits(tmp_path: Path) -> None:
    (tmp_path / "_common").mkdir(parents=True)
    (tmp_path / "_common" / "base.md").write_text("MINE", encoding="utf-8")
    FilesystemWorkflowSourceAdapter(tmp_path).seed()
    assert (tmp_path / "_common" / "base.md").read_text(encoding="utf-8") == "MINE"


def test_find_and_create(tmp_path: Path) -> None:
    source = FilesystemWorkflowSourceAdapter(tmp_path)
    assert source.find("doc-review") is None
    folder = source.create("doc-review")
    assert Path(folder) == tmp_path / "doc-review"
    # No per-workflow rules folder: a workflow that behaves wrongly is fixed in the workflow.
    assert not (tmp_path / "doc-review" / "rules").exists()
    assert source.find("doc-review") is None  # still no workflow.md
    (tmp_path / "doc-review" / "workflow.md").write_text("# doc-review", encoding="utf-8")
    assert source.find("doc-review") is not None


def test_create_draft_makes_a_sibling_folder_outside_workflows(tmp_path: Path) -> None:
    source = FilesystemWorkflowSourceAdapter(tmp_path / "workflows")
    draft = source.create_draft("create-workflow_001")
    assert Path(draft) == tmp_path / "drafts" / "create-workflow_001"  # a sibling of workflows/
    assert Path(draft).is_dir()
    assert not (Path(draft) / "rules").exists()  # rules are never workflow-scoped


def test_read_draft_marker_parses_a_finished_marker(tmp_path: Path) -> None:
    source = FilesystemWorkflowSourceAdapter(tmp_path / "workflows")
    draft = Path(source.create_draft("create-workflow_001"))
    (draft / "meta.json").write_text('{"name": "nightly-etl", "status": "finished"}', "utf-8")
    marker = source.read_draft_marker(str(draft))
    assert marker == DraftMarker("nightly-etl", finished=True)


def test_read_draft_marker_tolerates_absent_or_malformed(tmp_path: Path) -> None:
    source = FilesystemWorkflowSourceAdapter(tmp_path / "workflows")
    draft = Path(source.create_draft("create-workflow_001"))
    assert source.read_draft_marker(str(draft)) == DraftMarker(None, finished=False)  # no file
    (draft / "meta.json").write_text("not json", encoding="utf-8")
    assert source.read_draft_marker(str(draft)) == DraftMarker(None, finished=False)  # bad json
    (draft / "meta.json").write_text('{"name": "x"}', encoding="utf-8")  # no status
    assert source.read_draft_marker(str(draft)) == DraftMarker("x", finished=False)
    (draft / "meta.json").write_text('{"status": "finished"}', encoding="utf-8")  # no name
    assert source.read_draft_marker(str(draft)) == DraftMarker(None, finished=True)


def test_deploy_draft_moves_the_draft_and_drops_the_marker(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    source = FilesystemWorkflowSourceAdapter(workflows)
    draft = Path(source.create_draft("create-workflow_001"))
    (draft / "workflow.md").write_text("# nightly-etl", encoding="utf-8")
    (draft / "meta.json").write_text(
        '{"label": "Nightly ETL", "description": "Runs nightly.", "status": "finished"}', "utf-8"
    )

    deployed = source.deploy_draft(
        str(draft), "nightly-etl", "Nightly ETL", "Runs nightly.", "2026-07-29T09:00:00+00:00"
    )

    deployed_dir = workflows / "nightly-etl"
    assert Path(deployed) == deployed_dir
    assert (deployed_dir / "workflow.md").read_text(encoding="utf-8") == "# nightly-etl"
    assert not (deployed_dir / "meta.json").exists()  # transient marker stripped
    assert not draft.exists()  # the draft was moved, not copied
    found = source.find("nightly-etl")
    assert found is not None
    assert found.slug == "nightly-etl"


def _add_workflow(root: Path, name: str) -> None:
    (root / name).mkdir(parents=True, exist_ok=True)
    (root / name / "workflow.md").write_text(f"# {name}", encoding="utf-8")


def test_names_lists_runnable_workflows_sorted(tmp_path: Path) -> None:
    source = FilesystemWorkflowSourceAdapter(tmp_path)
    assert source.names() == []
    _add_workflow(tmp_path, "release")
    _add_workflow(tmp_path, "doc-review")
    assert source.names() == ["doc-review", "release"]


def test_names_hides_base_meta_and_folders_without_workflow_md(tmp_path: Path) -> None:
    source = FilesystemWorkflowSourceAdapter(tmp_path)
    source.seed()  # brings in _common and create-workflow
    _add_workflow(tmp_path, "doc-review")
    (tmp_path / "half-made").mkdir()  # no workflow.md yet
    assert source.names() == ["doc-review"]


def test_compile_joins_base_and_steps(tmp_path: Path) -> None:
    source = FilesystemWorkflowSourceAdapter(tmp_path)
    source.seed()
    (tmp_path / "doc-review").mkdir()
    (tmp_path / "doc-review" / "workflow.md").write_text("# doc-review steps", encoding="utf-8")
    compiled = source.compile(CompileMode.WORKFLOW, "doc-review")
    assert "How to run a workflow" in compiled  # from base.md
    # the rule-capture directive now rides the always-on rules group, not base.md
    assert "Rules — the user's demanded reflexes" in compiled
    assert "# doc-review steps" in compiled


def test_compile_includes_profile_and_rules_in_order(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    profile = tmp_path / "profile"
    environments = tmp_path / "environments"
    env_rules = environments / "work" / "rules"
    for folder in (profile / "me", env_rules):
        folder.mkdir(parents=True)
    (profile / "me" / "bio.md").write_text("# Me\nI work in French.", encoding="utf-8")
    (profile / "me" / "prefs.md").write_text("I prefer tests first.", encoding="utf-8")
    # Place-specific context now lives under the active environment (defaults to "work").
    (environments / "work" / "stack.md").write_text("# Company\nUse hexagonal.", encoding="utf-8")
    (env_rules / "test-first.rule.md").write_text(
        "---\nname: test-first\nstatus: active\n---\n\n**Rule:** test first.\n\n"
        "**Origin:** learned the hard way.",
        encoding="utf-8",
    )
    _add_workflow(workflows, "doc-review")

    source = FilesystemWorkflowSourceAdapter(workflows, profile, environments_root=environments)
    compiled = source.compile(CompileMode.WORKFLOW, "doc-review")

    assert "I work in French." in compiled
    assert "I prefer tests first." in compiled  # second file in profile/me/
    assert "Use hexagonal." in compiled
    assert "**Rule:** test first." in compiled
    assert "learned the hard way." not in compiled  # the rule's Origin content is cleaned
    # The rule's own frontmatter is cleaned. (Not asserted on "status:" — the directive
    # embeds the rule *template*, which legitimately shows the frontmatter block.)
    assert "name: test-first" not in compiled
    # order: profile before the workflow's own steps
    assert compiled.index("I work in French.") < compiled.index("# doc-review")


def test_compile_skips_draft_rules(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    environments = tmp_path / "environments"
    env_rules = environments / "work" / "rules"
    env_rules.mkdir(parents=True)
    (env_rules / "draft.rule.md").write_text(
        "---\nname: d\nstatus: draft\n---\n\n**Rule:** not yet.", encoding="utf-8"
    )
    _add_workflow(workflows, "doc-review")
    compiled = FilesystemWorkflowSourceAdapter(
        workflows, None, environments_root=environments
    ).compile(CompileMode.WORKFLOW, "doc-review")
    assert "not yet" not in compiled


def test_default_mode_composes_profile_and_rules_not_the_workflow(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    environments = tmp_path / "environments"
    env_rules = environments / "work" / "rules"
    (profile / "me").mkdir(parents=True)
    env_rules.mkdir(parents=True)
    (profile / "me" / "bio.md").write_text("I like short answers.", encoding="utf-8")
    (environments / "work" / "co.md").write_text("ACME Corp.", encoding="utf-8")
    (env_rules / "r.rule.md").write_text("**Rule:** be careful.", encoding="utf-8")
    workflows = tmp_path / "workflows"
    (workflows / "_common").mkdir(parents=True)
    (workflows / "_common" / "base.md").write_text("How to run a workflow", encoding="utf-8")

    compiled = FilesystemWorkflowSourceAdapter(
        workflows, profile, environments_root=environments
    ).compile(CompileMode.DEFAULT)

    assert "I like short answers." in compiled  # me.user, on by default
    assert "ACME Corp." in compiled  # company, on by default
    assert "How to run a workflow" not in compiled  # base is workflow-only
    # rules — and the always-on capture directive — are now on by default in a plain session
    assert "be careful" in compiled
    assert "Rules — the user's demanded reflexes" in compiled


def _write_role_content(profile: Path, role: str) -> None:
    """Seed a role's scoped rule and learned notebook under profile/roles/<role>/."""
    role_rules = profile / "roles" / role / "rules"
    role_rules.mkdir(parents=True)
    (role_rules / "review.rule.md").write_text(
        "---\nname: role-review\nstatus: active\n---\n\n**Rule:** engineer reviews diffs.",
        encoding="utf-8",
    )
    (profile / "roles" / role / "learned.md").write_text(
        "This engineer prefers property tests.", encoding="utf-8"
    )


def test_active_role_scopes_rules_and_learned_into_the_context(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    (profile / "me").mkdir(parents=True)
    (profile / "me" / "learned.md").write_text("Global note.", encoding="utf-8")
    environments = tmp_path / "environments"
    env_rules = environments / "work" / "rules"
    env_rules.mkdir(parents=True)
    (env_rules / "g.rule.md").write_text("**Rule:** lint with the house config.", "utf-8")
    _write_role_content(profile, "engineer")

    compiled = FilesystemWorkflowSourceAdapter(
        tmp_path / "wf", profile, environments_root=environments, default_role=lambda: "engineer"
    ).compile(CompileMode.DEFAULT)

    assert "lint with the house config." in compiled  # the environment's constraint
    assert "engineer reviews diffs." in compiled  # the active role's scoped rule
    assert "Global note." in compiled  # the shared learned notebook
    assert "prefers property tests." in compiled  # the active role's learned notebook
    # The role's preferences come first; the environment's constraints outrank them and so
    # sit last, closest to the model.
    assert compiled.index("engineer reviews diffs.") < compiled.index("lint with the house")


def test_inactive_role_content_is_not_composed(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    (profile / "me").mkdir(parents=True)
    _write_role_content(profile, "qa")  # content exists under roles/qa/ ...

    # ... but the active role is "default", so none of qa's scoped content is pulled in.
    compiled = FilesystemWorkflowSourceAdapter(
        tmp_path / "wf", profile, default_role=lambda: "default"
    ).compile(CompileMode.DEFAULT)

    assert "engineer reviews diffs." not in compiled
    assert "prefers property tests." not in compiled


def test_role_rules_skip_drafts_like_global_rules(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    role_rules = profile / "roles" / "engineer" / "rules"
    role_rules.mkdir(parents=True)
    (role_rules / "draft.rule.md").write_text(
        "---\nname: d\nstatus: draft\n---\n\n**Rule:** not yet.", encoding="utf-8"
    )
    compiled = FilesystemWorkflowSourceAdapter(
        tmp_path / "wf", profile, default_role=lambda: "engineer"
    ).compile(CompileMode.DEFAULT)
    assert "not yet" not in compiled  # a draft role rule is not injected


def test_rule_capture_directive_is_present_with_no_rules_yet(tmp_path: Path) -> None:
    # The whole point of always-on capture: offer to record the *first* rule, so the
    # directive must show even when the rules directory is empty.
    workflows = tmp_path / "workflows"
    rules = tmp_path / "rules"
    rules.mkdir()
    compiled = FilesystemWorkflowSourceAdapter(workflows, None, rules).compile(CompileMode.DEFAULT)
    assert "Rules — the user's demanded reflexes" in compiled


def test_rule_capture_directive_is_absent_when_rules_deactivated(tmp_path: Path) -> None:
    environments = tmp_path / "environments"
    env_rules = environments / "work" / "rules"
    env_rules.mkdir(parents=True)
    (env_rules / "r.rule.md").write_text("**Rule:** be careful.", encoding="utf-8")

    def _off(mode: str) -> dict[str, config.SourceSetting]:
        # Both axes off — the directive is suppressed only when neither is active.
        settings = config.default_startup(mode)
        off = config.SourceSetting(activated=False, compression=False)
        settings["rules.environment"] = off
        settings["rules.role"] = off
        return settings

    compiled = FilesystemWorkflowSourceAdapter(
        tmp_path / "wf", None, environments_root=environments, startup=_off
    ).compile(CompileMode.DEFAULT)
    assert "Rules — the user's demanded reflexes" not in compiled
    assert "be careful" not in compiled  # deactivating rules drops content and directive both


def test_learned_notebook_injects_the_capture_directive_and_notes(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    (profile / "me").mkdir(parents=True)
    (profile / "me" / "learned.md").write_text(
        "## What follows you\n\n- Prefers tests first.\n", encoding="utf-8"
    )
    compiled = FilesystemWorkflowSourceAdapter(tmp_path / "wf", profile).compile(
        CompileMode.DEFAULT
    )
    assert "~/.gmlw/profile/me/learned.md" in compiled  # the directive names the notebook
    assert "as valuable as the positives" in compiled  # negatives-first-class directive
    assert "Prefers tests first." in compiled  # the user's own note


def test_learned_section_is_invisible_without_a_notebook(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    environments = tmp_path / "environments"
    (environments / "work").mkdir(parents=True)
    (environments / "work" / "co.md").write_text("ACME.", encoding="utf-8")
    compiled = FilesystemWorkflowSourceAdapter(
        tmp_path / "wf", profile, environments_root=environments
    ).compile(CompileMode.DEFAULT)
    assert "learned.md" not in compiled  # no notebook -> no directive
    assert "ACME." in compiled  # other sources unaffected


def test_me_user_excludes_learned_which_me_learned_reads(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    (profile / "me").mkdir(parents=True)
    (profile / "me" / "bio.md").write_text("USER FACT", encoding="utf-8")
    (profile / "me" / "learned.md").write_text("LEARNED FACT", encoding="utf-8")
    (profile / "me" / "learned").mkdir()
    (profile / "me" / "learned" / "pref.md").write_text("LEARNED DIR FACT", encoding="utf-8")

    compiled = FilesystemWorkflowSourceAdapter(tmp_path / "wf", profile).compile(
        CompileMode.DEFAULT
    )

    assert "USER FACT" in compiled
    assert "LEARNED DIR FACT" in compiled  # me.learned reads the learned/ folder too
    assert compiled.count("LEARNED FACT") == 1  # learned.md read once (me.learned), not by me.user


class _FakePersonas(PersonaSourcePort):
    def __init__(self, personas: dict[str, Persona], floor: str = "FLOOR") -> None:
        self._personas = personas
        self._floor = floor

    def seed(self) -> None:
        pass

    def available(self) -> list[Persona]:
        return list(self._personas.values())

    def get(self, name: str) -> Persona | None:
        return self._personas.get(name)

    def floor(self) -> str:
        return self._floor


def _persona_on(mode: str) -> dict[str, config.SourceSetting]:
    # Persona on, both rule axes off — these tests isolate persona composition, so the
    # always-on rule-capture directive (default in every mode) is switched off to keep
    # them focused. The directive is suppressed only when *neither* axis is active.
    settings = config.default_startup(mode)
    settings["persona"] = config.SourceSetting(activated=True, compression=False)
    off = config.SourceSetting(activated=False, compression=False)
    settings["rules.environment"] = off
    settings["rules.role"] = off
    return settings


def test_selected_persona_is_composed_with_the_floor_when_active(tmp_path: Path) -> None:
    personas = _FakePersonas({"butler": Persona("butler", "d", "g", "BUTLER TONE")})
    source = FilesystemWorkflowSourceAdapter(
        tmp_path / "wf", personas=personas, startup=_persona_on, companion=lambda: "butler"
    )
    compiled = source.compile(CompileMode.DEFAULT)
    assert "BUTLER TONE" in compiled
    assert "FLOOR" in compiled  # the universal floor is composed beneath the persona


def test_persona_is_invisible_when_none_selected(tmp_path: Path) -> None:
    personas = _FakePersonas({"butler": Persona("butler", "d", "g", "BUTLER TONE")})
    source = FilesystemWorkflowSourceAdapter(
        tmp_path / "wf", personas=personas, startup=_persona_on, companion=lambda: None
    )
    compiled = source.compile(CompileMode.DEFAULT)
    assert "BUTLER TONE" not in compiled
    assert "FLOOR" not in compiled  # no selection -> not even the floor


def test_unknown_persona_selection_is_invisible(tmp_path: Path) -> None:
    personas = _FakePersonas({"butler": Persona("butler", "d", "g", "BUTLER TONE")})
    source = FilesystemWorkflowSourceAdapter(
        tmp_path / "wf", personas=personas, startup=_persona_on, companion=lambda: "ghost"
    )
    # An unknown persona composes nothing; the session snapshot is always present, so the
    # assertion is that no *character* reached the context, not that the context is empty.
    assert "BUTLER TONE" not in source.compile(CompileMode.DEFAULT)


def test_persona_off_by_default_even_when_selected(tmp_path: Path) -> None:
    personas = _FakePersonas({"butler": Persona("butler", "d", "g", "BUTLER TONE")})
    source = FilesystemWorkflowSourceAdapter(
        tmp_path / "wf", personas=personas, companion=lambda: "butler"
    )  # default matrix has persona activated = False
    assert "BUTLER TONE" not in source.compile(CompileMode.DEFAULT)


class _RecordingCompressor(ContextCompressorPort):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def compress(self, text: str, *, source_key: str, kind: str | None) -> str:
        self.calls.append((source_key, kind))
        return f"Z({source_key})"


def test_typed_compression_applies_per_source_only_when_flagged(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    environments = tmp_path / "environments"
    (profile / "me").mkdir(parents=True)
    (environments / "work").mkdir(parents=True)
    (profile / "me" / "bio.md").write_text("ME", encoding="utf-8")
    (environments / "work" / "co.md").write_text("CO", encoding="utf-8")
    compressor = _RecordingCompressor()

    def startup(mode: str) -> dict[str, config.SourceSetting]:
        settings = config.default_startup(mode)
        settings["me.user"] = config.SourceSetting(activated=True, compression=True)
        settings["company"] = config.SourceSetting(activated=True, compression=False)
        return settings

    compiled = FilesystemWorkflowSourceAdapter(
        tmp_path / "wf",
        profile,
        compressor=compressor,
        startup=startup,
        environments_root=environments,
    ).compile(CompileMode.DEFAULT)

    assert "Z(me.user)" in compiled  # me.user compressed with its human-touch kind
    assert "CO" in compiled  # company left verbatim (compression off)
    assert compressor.calls == [("me.user", "human-touch")]  # only the flagged source


def test_config_can_deactivate_a_source(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    (profile / "company").mkdir(parents=True)
    (profile / "company" / "co.md").write_text("CO", encoding="utf-8")

    def startup(mode: str) -> dict[str, config.SourceSetting]:
        settings = config.default_startup(mode)
        settings["company"] = config.SourceSetting(activated=False, compression=False)
        return settings

    source = FilesystemWorkflowSourceAdapter(tmp_path / "wf", profile, startup=startup)
    assert "CO" not in source.compile(CompileMode.DEFAULT)


class _Marker(InterceptorPort):
    def __init__(self, mark: str) -> None:
        self._mark = mark

    def intercept(self, text: str, target: str) -> str:
        return f"{self._mark}({text})" if text else text


def test_compile_runs_interceptors_per_target(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    environments = tmp_path / "environments"
    env_rules = environments / "work" / "rules"
    env_rules.mkdir(parents=True)
    (env_rules / "r.rule.md").write_text("**Rule:** be careful.", encoding="utf-8")
    _add_workflow(workflows, "doc-review")
    chain = InterceptorChain([("rules", _Marker("RULES")), ("context", _Marker("CTX"))])

    compiled = FilesystemWorkflowSourceAdapter(
        workflows, None, interceptors=chain, environments_root=environments
    ).compile(CompileMode.WORKFLOW, "doc-review")

    # the rules target wraps the whole rules group: the capture directive, then the rule
    assert "RULES(## Rules — the user's demanded reflexes" in compiled
    assert "**Rule:** be careful.)" in compiled  # rule is the tail of the wrapped group
    assert compiled.startswith("CTX(")  # context target wrapped the whole compiled blob


def test_compiled_context_opens_with_the_session_snapshot(tmp_path: Path) -> None:
    """The snapshot leads, carrying the live selections and the job it was compiled for."""
    source = FilesystemWorkflowSourceAdapter(
        tmp_path / "wf",
        default_environment=lambda: "work",
        default_role=lambda: "software-engineer",
        companion=lambda: "butler",
        user_name=lambda: "Daniel",
        language=lambda: "fr",
    )
    compiled = source.compile(CompileMode.DEFAULT, job="nightly-etl")

    assert compiled.startswith("## This session")  # frames everything after it
    payload = json.loads(compiled.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert payload == {
        "user_name": "Daniel",
        "user_prefered_language": "fr",
        "user_environment": "work",
        "user_role": "software-engineer",
        "ai_persona": "butler",
        "job_name": "nightly-etl",
    }


def test_snapshot_renders_unset_selections_as_empty(tmp_path: Path) -> None:
    """An unwired source still emits the block, so the shape never varies."""
    compiled = FilesystemWorkflowSourceAdapter(tmp_path / "wf").compile(CompileMode.DEFAULT)
    payload = json.loads(compiled.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert payload["ai_persona"] == ""
    assert payload["job_name"] == ""
    assert payload["user_environment"] == "work"  # the built-in default


# ── the label/description sidecar ──
def test_deploying_records_the_label_and_description_beside_the_slug(tmp_path: Path) -> None:
    source = FilesystemWorkflowSourceAdapter(tmp_path / "workflows")
    draft = Path(source.create_draft("create-workflow_001"))
    (draft / "workflow.md").write_text("# steps", encoding="utf-8")
    source.deploy_draft(
        str(draft), "nightly-etl", "Nightly ETL", "Runs the ETL overnight.", "2026-07-29T09:00:00Z"
    )
    catalog = source.catalog()
    assert catalog == [
        Workflow(slug="nightly-etl", label="Nightly ETL", description="Runs the ETL overnight.")
    ]


def test_a_workflow_without_a_sidecar_reports_its_slug_as_its_label(tmp_path: Path) -> None:
    # Everything authored before the sidecar existed. Nothing is migrated: it lists
    # exactly as it always did.
    root = tmp_path / "workflows"
    (root / "legacy").mkdir(parents=True)
    (root / "legacy" / "workflow.md").write_text("# steps", encoding="utf-8")
    assert FilesystemWorkflowSourceAdapter(root).catalog() == [
        Workflow(slug="legacy", label="legacy", description="")
    ]


def test_a_malformed_sidecar_degrades_to_the_slug(tmp_path: Path) -> None:
    root = tmp_path / "workflows"
    (root / "broken").mkdir(parents=True)
    (root / "broken" / "workflow.md").write_text("# steps", encoding="utf-8")
    (root / "broken" / ".about.toml").write_text("not = [valid", encoding="utf-8")
    assert FilesystemWorkflowSourceAdapter(root).catalog() == [
        Workflow(slug="broken", label="broken", description="")
    ]


def test_the_marker_carries_the_label_and_description(tmp_path: Path) -> None:
    source = FilesystemWorkflowSourceAdapter(tmp_path / "workflows")
    draft = Path(source.create_draft("create-workflow_001"))
    (draft / "meta.json").write_text(
        '{"label": "Nightly ETL", "description": "Overnight.", "status": "finished"}',
        encoding="utf-8",
    )
    marker = source.read_draft_marker(str(draft))
    assert marker.label == "Nightly ETL"
    assert marker.description == "Overnight."
    assert marker.finished is True


def test_an_older_marker_with_only_a_name_still_parses(tmp_path: Path) -> None:
    # Interviews written before labels existed wrote a bare kebab-case name.
    source = FilesystemWorkflowSourceAdapter(tmp_path / "workflows")
    draft = Path(source.create_draft("create-workflow_001"))
    (draft / "meta.json").write_text('{"name": "nightly-etl", "status": "finished"}', "utf-8")
    marker = source.read_draft_marker(str(draft))
    assert marker.name == "nightly-etl"
    assert marker.label is None
    assert marker.description == ""


def test_find_returns_the_workflow_with_the_words_behind_its_slug(tmp_path: Path) -> None:
    """A yes/no would have made the caller ask a second question to learn anything."""
    folder = tmp_path / "nightly-etl"
    folder.mkdir(parents=True)
    (folder / "workflow.md").write_text("# steps", encoding="utf-8")
    (folder / ".about.toml").write_text(
        'label = "Nightly ETL"\ndescription = "Loads yesterday."\n', encoding="utf-8"
    )

    found = FilesystemWorkflowSourceAdapter(tmp_path).find("nightly-etl")

    assert found is not None
    assert (found.slug, found.label, found.description) == (
        "nightly-etl",
        "Nightly ETL",
        "Loads yesterday.",
    )


def test_a_folder_with_no_steps_file_is_not_a_workflow(tmp_path: Path) -> None:
    (tmp_path / "half-made").mkdir(parents=True)

    assert FilesystemWorkflowSourceAdapter(tmp_path).find("half-made") is None


def test_the_shared_base_and_the_meta_workflow_are_never_found(tmp_path: Path) -> None:
    """Hidden from this the same way they are hidden from the listing.

    Otherwise a caller could be handed one of them as if it were a workflow of the user's
    own — which is what let ``--workflow create-workflow`` be accepted before.
    """
    source = FilesystemWorkflowSourceAdapter(tmp_path)
    source.seed()

    assert source.find("_common") is None
    assert source.find("create-workflow") is None
