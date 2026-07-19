# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for reading, seeding, and compiling workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.context_source import CompileMode
    from generic_ml_wrapper.application.domain.model.draft import DraftMarker


class WorkflowSourcePort(ABC):
    """Seed default workflows, check/create workflow folders, and compile context."""

    @abstractmethod
    def seed(self) -> None:
        """Copy the packaged default workflows into the user's home, missing-only."""

    @abstractmethod
    def names(self) -> list[str]:
        """Return the names of the runnable workflows, sorted.

        Excludes the shared base and the create-workflow meta-workflow.

        Returns:
            The runnable workflow names (empty if none exist).
        """

    @abstractmethod
    def exists(self, name: str) -> bool:
        """Return whether a runnable workflow exists.

        Args:
            name: The workflow name.

        Returns:
            ``True`` if the workflow has a ``workflow.md``.
        """

    @abstractmethod
    def create(self, name: str) -> str:
        """Create an empty folder for a new workflow.

        Args:
            name: The workflow name.

        Returns:
            The absolute path to the created folder.
        """

    @abstractmethod
    def folder(self, name: str) -> str:
        """Return a workflow's folder path without creating or modifying anything.

        Args:
            name: The workflow name.

        Returns:
            The absolute path to the workflow's folder (whether or not it exists).
        """

    @abstractmethod
    def create_draft(self, key: str) -> str:
        """Create a scratch draft folder for an in-progress workflow.

        A workflow is authored here (its name is decided at the end) before being
        deployed into ``workflows/<name>/``. The draft lives outside ``workflows/`` so
        a half-authored one never appears as runnable.

        Args:
            key: A unique key for the draft (the authoring session id).

        Returns:
            The absolute path to the created draft folder.
        """

    @abstractmethod
    def read_draft_marker(self, draft_path: str) -> DraftMarker:
        """Read the convergence marker an authoring session left in its draft folder.

        Args:
            draft_path: The draft folder returned by :meth:`create_draft`.

        Returns:
            The parsed marker; a missing or malformed one yields
            ``DraftMarker(None, finished=False)`` (an incomplete draft).
        """

    @abstractmethod
    def deploy_draft(self, draft_path: str, name: str) -> str:
        """Move a finished draft into ``workflows/<name>/``.

        The move is atomic (a directory rename on the same filesystem). The caller is
        responsible for validating the name and confirming it is free first.

        Args:
            draft_path: The draft folder to deploy.
            name: The workflow name to deploy it as.

        Returns:
            The absolute path to the deployed workflow folder.
        """

    @abstractmethod
    def meta_guide(self) -> str:
        """Return the create-workflow guided-facilitation supplement, or ``""``.

        The facilitation layer injected on top of the core interview when a user picks
        the guided authoring experience. Absent (empty) if the file is not present.

        Returns:
            The guide text, or ``""`` when there is none.
        """

    @abstractmethod
    def compile(self, mode: CompileMode, name: str | None = None) -> str:
        """Compile a run's operating context for a mode.

        The activation matrix for the mode selects which cross-cutting sources
        (persona, profile, learned, company, rules) are composed and whether each is
        compressed. A workflow/authoring run additionally composes the workflow's
        base, its steps, and its scoped rules.

        Args:
            mode: The compile mode (default/workflow/authoring).
            name: The workflow whose base/steps/rules to compose, for the
                workflow/authoring modes; ``None`` for a plain (default) run.

        Returns:
            The composed context (active sources, joined by blank lines).
        """
