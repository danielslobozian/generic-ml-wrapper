# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``LocalGitWorkspaceInspector``: read the folder and git state from the cwd."""

from __future__ import annotations

import subprocess
from pathlib import Path

from generic_ml_wrapper.application.domain.model.workspace import Workspace
from generic_ml_wrapper.application.port.outbound.workspace import WorkspaceInspectorPort

_GIT_TIMEOUT_SECONDS = 2


class LocalGitWorkspaceInspector(WorkspaceInspectorPort):
    """Inspect the working directory and, when it is a git repository, git state.

    The status-line command runs in the client's working directory, so the folder
    comes from :func:`Path.cwd` and the git facts from ``git`` invoked there. Git
    calls are best-effort: any failure (not a repository, git absent, a slow call)
    leaves that field empty rather than raising.
    """

    def inspect(self) -> Workspace:
        """Inspect the current working directory and its git state.

        Returns:
            The folder (home abbreviated) and git state; git fields are ``None``
            outside a repository and ``dirty`` is ``0`` when clean or unknown.
        """
        branch = _git("branch", "--show-current")
        if branch is None:
            return Workspace(folder=_folder(), repo=None, branch=None, short_sha=None, dirty=0)
        toplevel = _git("rev-parse", "--show-toplevel")
        porcelain = _git("status", "--porcelain")
        return Workspace(
            folder=_folder(),
            repo=Path(toplevel).name if toplevel else None,
            branch=branch,
            short_sha=_git("rev-parse", "--short", "HEAD"),
            dirty=len(porcelain.splitlines()) if porcelain else 0,
        )


def _folder() -> str | None:
    try:
        cwd = Path.cwd()
    except OSError:
        return None
    home = Path.home()
    if cwd == home:
        return "~"
    try:
        return "~/" + cwd.relative_to(home).as_posix()
    except ValueError:
        return str(cwd)


def _git(*args: str) -> str | None:
    try:
        # Trusted argv: a fixed ``git`` program with our own literal arguments.
        completed = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    stripped = completed.stdout.strip()
    return stripped or None
