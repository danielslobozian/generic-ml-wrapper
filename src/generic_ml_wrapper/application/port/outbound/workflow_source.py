# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for reading, seeding, and compiling workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.context_source import CompileMode


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
