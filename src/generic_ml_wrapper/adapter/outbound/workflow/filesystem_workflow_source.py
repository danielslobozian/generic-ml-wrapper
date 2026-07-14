# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Filesystem ``WorkflowSourcePort``: workflows under ``~/.gmlw/workflows``."""

from __future__ import annotations

from importlib import resources
from importlib.abc import Traversable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.domain.service.rule_cleaner import clean_rule
from generic_ml_wrapper.application.port.outbound.workflow_source import WorkflowSourcePort

_COMMON = "_common"
_META = "create-workflow"
_HIDDEN = frozenset({_COMMON, _META})
_PROFILE_SUBDIRS = ("me", "company")
_STRIP_SECTIONS = ("Origin", "Notes")


class FilesystemWorkflowSource(WorkflowSourcePort):
    """Read workflows from ``<root>/<name>/workflow.md``; seed packaged defaults.

    ``compile`` assembles a workflow's operating context from several locations —
    the shared base, the user's profile, the global and per-workflow rules, and the
    workflow's steps.
    """

    def __init__(
        self,
        root: Path,
        profile_root: Path | None = None,
        rules_root: Path | None = None,
        interceptors: InterceptorChain | None = None,
    ) -> None:
        """Bind the source to its roots.

        Args:
            root: The directory holding one folder per workflow.
            profile_root: The user's profile directory, or ``None`` to omit it.
            rules_root: The global rules directory, or ``None`` to omit it.
            interceptors: The per-section interceptor chain, or ``None`` for none.
        """
        self._root = root
        self._profile_root = profile_root
        self._rules_root = rules_root
        self._interceptors = interceptors or InterceptorChain(())

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

    def compile(self, name: str) -> str:
        """Compile a workflow's operating context, in a fixed order.

        The order is: shared base, the user's profile, the global rules, the
        workflow's own rules, then the workflow's steps. Missing sections are
        skipped; rules are cleaned (frontmatter and human-only notes dropped). Each
        section passes through the interceptor chain for its target, and the joined
        result through the ``context`` target.

        Args:
            name: The workflow name.

        Returns:
            The concatenated context (sections that exist, joined by blank lines).
        """
        profile = self._interceptors.apply("profile", self._profile())
        rules = self._interceptors.apply("rules", self._combined_rules(name))
        workflow = self._interceptors.apply(
            "workflow", self._read(self._root / name / "workflow.md")
        )
        parts = [self._read(self._root / _COMMON / "base.md"), profile, rules, workflow]
        context = "\n\n\n".join(part for part in parts if part)
        return self._interceptors.apply("context", context)

    def _combined_rules(self, name: str) -> str:
        parts = [self._rules(self._rules_root), self._rules(self._root / name / "rules")]
        return "\n\n\n".join(part for part in parts if part)

    def _profile(self) -> str:
        if self._profile_root is None:
            return ""
        pieces = [self._concat_dir(self._profile_root / subdir) for subdir in _PROFILE_SUBDIRS]
        return "\n\n".join(piece for piece in pieces if piece)

    def _concat_dir(self, directory: Path) -> str:
        """Concatenate every ``*.md`` in a profile subfolder, sorted by filename."""
        if not directory.is_dir():
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
