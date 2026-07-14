# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The Workspace value object: environment facts the wrapper reports itself."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Workspace:
    """The working environment a run executes in, computed by the wrapper.

    These facts are client-agnostic: the wrapper derives them from the working
    directory and git, so they enrich the status line the same way for every
    client. Each field is optional because the run may not be in a git repository
    (or in any resolvable directory at all).

    Attributes:
        folder: The working directory (home abbreviated to ``~``), or ``None``.
        repo: The git repository's name, or ``None`` outside a repository.
        branch: The checked-out branch, or ``None`` outside a repository.
        short_sha: The current commit's short hash, or ``None``.
        dirty: The count of uncommitted changes (``0`` when clean).
    """

    folder: str | None
    repo: str | None
    branch: str | None
    short_sha: str | None
    dirty: int
