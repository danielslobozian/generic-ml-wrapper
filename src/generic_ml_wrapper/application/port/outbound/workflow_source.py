# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for reading, seeding, and compiling workflows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.context_source import CompileMode
    from generic_ml_wrapper.application.domain.model.draft import Draft, DraftMarker
    from generic_ml_wrapper.application.domain.model.workflow import Workflow


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
    def find(self, name: str) -> Workflow | None:
        """Return the runnable workflow of that name, or ``None`` if there is none.

        Hands back the workflow rather than a yes/no, so a caller that has to know a
        workflow exists before acting on it does not then have to ask a second question to
        learn anything about it. ``None`` rather than an exception because what an absent
        workflow means differs by caller -- unknown to one, free to take to another -- and
        the caller is the one that knows which.

        Args:
            name: The workflow name.

        Returns:
            The workflow, or ``None`` when no runnable workflow has that name.
        """

    @abstractmethod
    def catalog(self) -> list[Workflow]:
        """Return the runnable workflows with the human words behind their slugs.

        The richer counterpart to :meth:`names`, for listings that show a workflow as its
        author described it. A workflow with no ``.about.toml`` reports its slug as its
        label and an empty description, so one authored before the sidecar existed still
        lists — unmigrated and unchanged.

        Returns:
            The workflows, sorted by slug (empty if none exist).
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
    def drafts(self) -> list[Draft]:
        """Return the drafts still on disk, newest first.

        Every authoring session that did not deploy leaves its folder behind, so this is
        the record of unfinished work. The folder name is the authoring session id, which
        is what lets a draft be reopened without a path having been stored anywhere.

        Returns:
            The drafts with their markers read, newest first (empty when there are none).
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
    def deploy_draft(
        self, draft_path: str, name: str, label: str, description: str, created: str
    ) -> str:
        """Move a finished draft into ``workflows/<name>/`` and record what it is.

        The move is atomic (a directory rename on the same filesystem). The caller is
        responsible for deriving the slug, validating it, and confirming it is free.

        The human words are written into the deployed folder's ``.about.toml``, the same
        sidecar roles and environments use — so the slug stays the id while the label and
        description stay readable.

        Args:
            draft_path: The draft folder to deploy.
            name: The slug to deploy it as (the folder name).
            label: The human name behind the slug.
            description: A fuller line, or empty when none was given.
            created: An ISO-8601 timestamp for when the workflow appeared.

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
    def compile(self, mode: CompileMode, name: str | None = None, job: str | None = None) -> str:
        """Compile a run's operating context for a mode.

        The context opens with the session snapshot — the active environment, role,
        persona and job — then the activation matrix for the mode selects which
        cross-cutting sources (persona, profile, learned, company, rules) are composed
        and whether each is compressed. A workflow/authoring run additionally composes
        the workflow's base and its steps.

        Args:
            mode: The compile mode (default/workflow/authoring).
            name: The workflow whose base/steps to compose, for the workflow/authoring
                modes; ``None`` for a plain (default) run.
            job: The job this session runs on, for the snapshot; ``None`` leaves the
                snapshot's ``job_name`` empty rather than omitting the block.

        Returns:
            The composed context (the snapshot, then the active sources).
        """
