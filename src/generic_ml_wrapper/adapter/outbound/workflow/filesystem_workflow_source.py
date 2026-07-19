# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``WorkflowSourcePort``: workflows under ``~/.gmlw/workflows``."""

from __future__ import annotations

import json
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import TYPE_CHECKING, cast

from generic_ml_wrapper.application.domain.model import context_source
from generic_ml_wrapper.application.domain.model.context_source import CompileMode, ContextSource
from generic_ml_wrapper.application.domain.model.draft import DraftMarker
from generic_ml_wrapper.application.domain.model.learned import CAPTURE_DIRECTIVE
from generic_ml_wrapper.application.domain.model.rules import RULE_CAPTURE_DIRECTIVE
from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.domain.service.rule_cleaner import clean_rule
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.common import config

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.application.port.outbound.context_compressor import (
        ContextCompressorPort,
    )
    from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort

_COMMON = "_common"
_META = "create-workflow"
_HIDDEN = frozenset({_COMMON, _META})
_LEARNED_FILE = "learned.md"
_LEARNED_DIR = "learned"
_STRIP_SECTIONS = ("Origin", "Notes")
_MARKER = "meta.json"
_FINISHED = "finished"
_GUIDE = "guided.md"


class FilesystemWorkflowSource(WorkflowSourcePort):
    """Read workflows from ``<root>/<name>/workflow.md``; seed packaged defaults.

    ``compile`` composes a run's operating context from several locations — the
    persona, the user's profile (self + learned + company), the global and
    per-workflow rules, and (for a workflow) the shared base and its steps. Which
    sources are active, and whether each is compressed, is decided per mode by the
    injected startup policy.
    """

    def __init__(  # noqa: PLR0913  (a composition adapter binding several ~/.gmlw roots)
        self,
        root: Path,
        profile_root: Path | None = None,
        rules_root: Path | None = None,
        interceptors: InterceptorChain | None = None,
        personas: PersonaSourcePort | None = None,
        compressor: ContextCompressorPort | None = None,
        startup: Callable[[str], dict[str, config.SourceSetting]] | None = None,
        companion: Callable[[], str | None] | None = None,
        environments_root: Path | None = None,
        default_environment: Callable[[], str] | None = None,
        default_role: Callable[[], str] | None = None,
    ) -> None:
        """Bind the source to its roots and context policy.

        Args:
            root: The directory holding one folder per workflow.
            profile_root: The user's profile directory, or ``None`` to omit it.
            rules_root: The global rules directory, or ``None`` to omit it.
            interceptors: The per-section interceptor chain, or ``None`` for none.
            personas: The persona source; the selected persona (plus the shared floor)
                is the ``persona`` context section. ``None`` omits the section.
            compressor: The typed compressor for per-source compression, or ``None``
                to leave every source verbatim.
            startup: Resolves a mode's activation matrix; defaults to the baked-in
                matrix (:func:`config.default_startup`), so the composition root
                injects :func:`config.startup` to honor the user's config file.
            companion: Resolves the selected persona name; defaults to none selected
                (the persona section stays invisible until the composition root injects
                :func:`config.companion`).
            environments_root: The environments directory holding one folder per
                environment; the ``company`` source reads the active one. ``None`` omits
                the source (place-specific context is off).
            default_environment: Resolves the active environment's name; defaults to
                ``"work"`` until the composition root injects
                :func:`config.default_environment`.
            default_role: Resolves the active role's name; the ``rules`` and ``me.learned``
                sources also read that role's ``profile/roles/<role>/`` folder. Defaults to
                ``"default"`` until the composition root injects :func:`config.default_role`.
        """
        self._root = root
        # In-progress drafts live in a sibling root (``~/.gmlw/drafts``), so a half-
        # authored workflow is never visible under ``workflows/`` until it is deployed.
        self._drafts_root = root.parent / "drafts"
        self._profile_root = profile_root
        self._rules_root = rules_root
        self._interceptors = interceptors or InterceptorChain(())
        self._personas = personas
        self._compressor = compressor
        self._startup = startup or config.default_startup
        self._companion = companion or (lambda: None)
        self._environments_root = environments_root
        self._default_environment = default_environment or (lambda: "work")
        self._default_role = default_role or (lambda: "default")

    def seed(self) -> None:
        """Copy the packaged default workflows into ``root``, never overwriting."""
        packaged = resources.files("generic_ml_wrapper").joinpath("resources", "workflows")
        self._copy_tree(packaged, self._root)

    def _copy_tree(self, source: Traversable, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        for entry in source.iterdir():
            target = destination / entry.name
            if entry.is_dir():
                self._copy_tree(entry, target)
            elif not target.exists():
                target.write_bytes(entry.read_bytes())

    def names(self) -> list[str]:
        """Return the runnable workflow names, sorted.

        A runnable workflow is a folder with a ``workflow.md`` that is neither the
        shared base nor the create-workflow meta-workflow.

        Returns:
            The runnable workflow names (empty if none exist).
        """
        if not self._root.is_dir():
            return []
        return sorted(
            child.name
            for child in self._root.iterdir()
            if child.name not in _HIDDEN and (child / "workflow.md").is_file()
        )

    def exists(self, name: str) -> bool:
        """Return whether ``<root>/<name>/workflow.md`` exists.

        Args:
            name: The workflow name.

        Returns:
            ``True`` if the workflow has a ``workflow.md``.
        """
        return (self._root / name / "workflow.md").is_file()

    def create(self, name: str) -> str:
        """Create ``<root>/<name>/`` (and its ``rules/`` folder).

        Args:
            name: The workflow name.

        Returns:
            The absolute path to the created folder.
        """
        folder = self._root / name
        (folder / "rules").mkdir(parents=True, exist_ok=True)
        return str(folder)

    def folder(self, name: str) -> str:
        """Return ``<root>/<name>`` without touching the filesystem.

        Args:
            name: The workflow name.

        Returns:
            The absolute path to the workflow's folder.
        """
        return str(self._root / name)

    def create_draft(self, key: str) -> str:
        """Create ``<drafts>/<key>/`` (and its ``rules/`` folder).

        Args:
            key: A unique key for the draft (the authoring session id).

        Returns:
            The absolute path to the created draft folder.
        """
        folder = self._drafts_root / key
        (folder / "rules").mkdir(parents=True, exist_ok=True)
        return str(folder)

    def read_draft_marker(self, draft_path: str) -> DraftMarker:
        """Read ``<draft>/meta.json`` into a :class:`DraftMarker`, tolerantly.

        A missing file, unreadable bytes, invalid JSON, or an unexpected shape all
        yield ``DraftMarker(None, finished=False)`` — an incomplete draft, left in place.

        Args:
            draft_path: The draft folder returned by :meth:`create_draft`.

        Returns:
            The parsed marker.
        """
        marker = Path(draft_path) / _MARKER
        try:
            data: object = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return DraftMarker(None, finished=False)
        if not isinstance(data, dict):
            return DraftMarker(None, finished=False)
        fields = cast("dict[str, object]", data)
        raw_name = fields.get("name")
        name = raw_name if isinstance(raw_name, str) and raw_name else None
        return DraftMarker(name, finished=fields.get("status") == _FINISHED)

    def deploy_draft(self, draft_path: str, name: str) -> str:
        """Move a finished draft into ``<root>/<name>/`` (an atomic directory rename).

        The transient marker is removed first so it does not linger in the deployed
        workflow. The caller must have validated the name and confirmed it is free.

        Args:
            draft_path: The draft folder to deploy.
            name: The workflow name to deploy it as.

        Returns:
            The absolute path to the deployed workflow folder.
        """
        draft = Path(draft_path)
        (draft / _MARKER).unlink(missing_ok=True)
        target = self._root / name
        self._root.mkdir(parents=True, exist_ok=True)
        draft.rename(target)
        return str(target)

    def meta_guide(self) -> str:
        """Return the create-workflow guided supplement (``guided.md``), or ``""``."""
        return self._read(self._root / _META / _GUIDE)

    def compile(self, mode: CompileMode, name: str | None = None) -> str:
        """Compose a run's operating context for a mode.

        The order is: profile family (persona, self, learned, company), then rules,
        then — for a workflow/authoring run — the base and steps. Each active source
        is optionally compressed (per its config), sections pass through the
        interceptor chain for their target, and the joined result through ``context``.

        Args:
            mode: The compile mode (default/workflow/authoring).
            name: The workflow whose base/steps/rules to compose, or ``None``.

        Returns:
            The composed context (active sections, joined by blank lines).
        """
        settings = self._startup(mode)
        profile = self._interceptors.apply("profile", self._profile_group(settings))
        rules = self._interceptors.apply("rules", self._rules_group(mode, name, settings))
        workflow = self._interceptors.apply("workflow", self._workflow_group(mode, name, settings))
        context = "\n\n\n".join(part for part in (profile, rules, workflow) if part)
        return self._interceptors.apply("context", context)

    def _profile_group(self, settings: dict[str, config.SourceSetting]) -> str:
        """Compose the active profile-family sources (persona, self, learned, company)."""
        parts: list[str] = []
        for source in context_source.PROFILE_FAMILY:
            setting = settings[source.key]
            if not setting.activated:
                continue
            text = self._maybe_compress(self._read_source(source), source, setting)
            if text:
                parts.append(text)
        return "\n\n".join(parts)

    def _rules_group(
        self, mode: CompileMode, name: str | None, settings: dict[str, config.SourceSetting]
    ) -> str:
        """Compose the rule-capture directive, the global rules, and any scoped rules.

        When the ``rules`` source is active for this mode, the section leads with the
        always-on capture directive (gmlw's voice) so a demanded correction becomes a
        draft rule in any session — even one with no rules yet. The directive stays
        verbatim; only the user's rule content is subject to compression.
        """
        setting = settings[context_source.RULES.key]
        if not setting.activated:
            return ""
        parts: list[str] = [RULE_CAPTURE_DIRECTIVE]
        global_rules = self._maybe_compress(
            self._rules(self._rules_root), context_source.RULES, setting
        )
        if global_rules:
            parts.append(global_rules)
        role_dir = self._role_dir()  # rules scoped to the active role, more specific than global
        if role_dir is not None:
            role_rules = self._maybe_compress(
                self._rules(role_dir / "rules"), context_source.RULES, setting
            )
            if role_rules:
                parts.append(role_rules)
        if context_source.includes_workflow(mode) and name:
            scoped = self._maybe_compress(
                self._rules(self._root / name / "rules"), context_source.RULES, setting
            )
            if scoped:
                parts.append(scoped)
        return "\n\n\n".join(parts)

    def _workflow_group(
        self, mode: CompileMode, name: str | None, settings: dict[str, config.SourceSetting]
    ) -> str:
        """Compose the shared base and the workflow's steps (workflow/authoring only)."""
        if not context_source.includes_workflow(mode):
            return ""
        parts: list[str] = []
        base = self._maybe_compress(
            self._read(self._root / _COMMON / "base.md"),
            context_source.BASE,
            settings[context_source.BASE.key],
        )
        if base:
            parts.append(base)
        if name:
            steps = self._maybe_compress(
                self._read(self._root / name / "workflow.md"),
                context_source.STEPS,
                settings[context_source.STEPS.key],
            )
            if steps:
                parts.append(steps)
        return "\n\n\n".join(parts)

    def _maybe_compress(
        self, text: str, source: ContextSource, setting: config.SourceSetting
    ) -> str:
        """Compress a source's text when its config asks and a compressor is wired."""
        if not (text and setting.compression) or self._compressor is None:
            return text
        return self._compressor.compress(text, source_key=source.key, kind=source.kind_name)

    def _read_source(self, source: ContextSource) -> str:
        """Read a profile-family source's raw text from its filesystem location."""
        if source is context_source.PERSONA:
            return self._persona()
        if source is context_source.ME_USER:
            return self._me_user()
        if source is context_source.ME_LEARNED:
            return self._me_learned()
        if source is context_source.COMPANY and self._environments_root is not None:
            # Place-specific context now lives per environment; read the active one. The
            # config key stays "company"; only its on-disk home moved (environments/<env>/).
            return self._concat_dir(self._environments_root / self._default_environment())
        return ""

    def _persona(self) -> str:
        """Compose the selected persona's tone body over the shared floor.

        Invisible (``""``) until a persona is selected and found: no source, no
        selection, or an unknown name all yield nothing, so a stranger is never
        greeted by a character.
        """
        if self._personas is None:
            return ""
        name = self._companion()
        if not name:
            return ""
        persona = self._personas.get(name)
        if persona is None:
            return ""
        parts = [persona.body, self._personas.floor()]
        return "\n\n---\n\n".join(part for part in parts if part)

    def _me_user(self) -> str:
        """Concatenate ``profile/me/*.md`` — the user about the user — excluding learned."""
        if self._profile_root is None:
            return ""
        directory = self._profile_root / "me"
        if not directory.is_dir():
            return ""
        texts = [
            self._read(path)
            for path in sorted(directory.glob("*.md"))
            if path.name != _LEARNED_FILE
        ]
        return "\n\n".join(text for text in texts if text)

    def _me_learned(self) -> str:
        """Compose the learned section: the capture directive over the user's notebooks.

        The notebook (``learned.md`` and any ``learned/`` folder) is the AI-about-the-user
        store; the directive (gmlw's voice) asks the client to keep mirroring into it. Both
        the shared ``profile/me`` notebook and the active role's ``profile/roles/<role>``
        notebook compose here (role notes are still learned — just scoped to the role); the
        directive stays global (capture is not role-aware yet). The section is invisible when
        both notebooks are absent, so a run without one stays clean.
        """
        if self._profile_root is None:
            return ""
        notebooks = [
            self._notebook(self._profile_root / "me"),
            self._notebook(self._profile_root / "roles" / self._default_role()),
        ]
        notebook = "\n\n".join(text for text in notebooks if text)
        return f"{CAPTURE_DIRECTIVE}\n\n{notebook}" if notebook else ""

    def _notebook(self, directory: Path) -> str:
        """Concatenate a learned notebook: ``learned.md`` then ``learned/*.md`` (sorted)."""
        parts: list[str] = []
        learned_file = directory / _LEARNED_FILE
        if learned_file.is_file():
            parts.append(self._read(learned_file))
        learned_dir = directory / _LEARNED_DIR
        if learned_dir.is_dir():
            parts += [self._read(path) for path in sorted(learned_dir.glob("*.md"))]
        return "\n\n".join(text for text in parts if text)

    def _role_dir(self) -> Path | None:
        """The active role's folder (``profile/roles/<role>``), or ``None`` without a profile."""
        if self._profile_root is None:
            return None
        return self._profile_root / "roles" / self._default_role()

    def _concat_dir(self, directory: Path | None) -> str:
        """Concatenate every ``*.md`` in a folder, sorted by filename."""
        if directory is None or not directory.is_dir():
            return ""
        files = [self._read(path) for path in sorted(directory.glob("*.md"))]
        return "\n\n".join(text for text in files if text)

    def _rules(self, directory: Path | None) -> str:
        if directory is None or not directory.is_dir():
            return ""
        cleaned: list[str] = []
        for path in sorted(directory.glob("*.rule.md")):
            raw = path.read_text(encoding="utf-8").strip()
            if raw and "status: draft" not in raw:
                rule = clean_rule(raw, _STRIP_SECTIONS)
                if rule:
                    cleaned.append(rule)
        return "\n\n---\n\n".join(cleaned)

    @staticmethod
    def _read(path: Path) -> str:
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8").strip()
