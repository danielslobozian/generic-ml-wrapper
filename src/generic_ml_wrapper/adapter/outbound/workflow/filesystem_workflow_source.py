# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``WorkflowSourcePort``: workflows under ``~/.gmlw/workflows``."""

from __future__ import annotations

from importlib import resources
from importlib.resources.abc import Traversable
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model import context_source
from generic_ml_wrapper.application.domain.model.context_source import CompileMode, ContextSource
from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.domain.service.rule_cleaner import clean_rule
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort
from generic_ml_wrapper.common import config

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from generic_ml_wrapper.application.port.outbound.context_compressor import (
        ContextCompressorPort,
    )

_COMMON = "_common"
_META = "create-workflow"
_HIDDEN = frozenset({_COMMON, _META})
_LEARNED_FILE = "learned.md"
_LEARNED_DIR = "learned"
_STRIP_SECTIONS = ("Origin", "Notes")


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
        persona_root: Path | None = None,
        compressor: ContextCompressorPort | None = None,
        startup: Callable[[str], dict[str, config.SourceSetting]] | None = None,
    ) -> None:
        """Bind the source to its roots and context policy.

        Args:
            root: The directory holding one folder per workflow.
            profile_root: The user's profile directory, or ``None`` to omit it.
            rules_root: The global rules directory, or ``None`` to omit it.
            interceptors: The per-section interceptor chain, or ``None`` for none.
            persona_root: The persona directory, or ``None`` to omit it.
            compressor: The typed compressor for per-source compression, or ``None``
                to leave every source verbatim.
            startup: Resolves a mode's activation matrix; defaults to the baked-in
                matrix (:func:`config.default_startup`), so the composition root
                injects :func:`config.startup` to honor the user's config file.
        """
        self._root = root
        self._profile_root = profile_root
        self._rules_root = rules_root
        self._interceptors = interceptors or InterceptorChain(())
        self._persona_root = persona_root
        self._compressor = compressor
        self._startup = startup or config.default_startup

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
        """Compose the global rules (when active) and, for a workflow, its scoped rules."""
        setting = settings[context_source.RULES.key]
        parts: list[str] = []
        if setting.activated:
            global_rules = self._maybe_compress(
                self._rules(self._rules_root), context_source.RULES, setting
            )
            if global_rules:
                parts.append(global_rules)
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
            return self._concat_dir(self._persona_root)
        if source is context_source.ME_USER:
            return self._me_user()
        if source is context_source.ME_LEARNED:
            return self._me_learned()
        if source is context_source.COMPANY and self._profile_root is not None:
            return self._concat_dir(self._profile_root / "company")
        return ""

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
        """Concatenate the learned notes — the AI about the user — file then folder."""
        if self._profile_root is None:
            return ""
        directory = self._profile_root / "me"
        parts: list[str] = []
        learned_file = directory / _LEARNED_FILE
        if learned_file.is_file():
            parts.append(self._read(learned_file))
        learned_dir = directory / _LEARNED_DIR
        if learned_dir.is_dir():
            parts += [self._read(path) for path in sorted(learned_dir.glob("*.md"))]
        return "\n\n".join(text for text in parts if text)

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
