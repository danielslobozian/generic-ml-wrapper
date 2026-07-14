# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for reading, seeding, and compiling workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod


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
    def compile(self, name: str) -> str:
        """Compile a workflow's operating context.

        Args:
            name: The workflow name.

        Returns:
            The shared base followed by the workflow's steps.
        """
