# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Pure rendering of the working environment and client status into one line."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_status import ClientStatus
    from generic_ml_wrapper.application.domain.model.workspace import Workspace

_SEPARATOR = "  ·  "


def render_statusline(status: ClientStatus, workspace: Workspace) -> str:
    """Render the working environment and client status as a single line.

    The wrapper's own facts (git, folder) come first, then the common client
    fields (model, context), then any client-specific ``extras`` (already
    formatted, e.g. Claude's quota), then cost. Blocks the environment or client
    did not provide are omitted, so a bare environment with an empty status yields
    an empty line.

    Args:
        status: The parsed client status.
        workspace: The working environment the wrapper computed.

    Returns:
        The status line (no trailing newline).
    """
    blocks = [
        _git(workspace),
        _folder(workspace),
        status.model,
        None if status.context_pct is None else f"ctx {status.context_pct}%",
        *status.extras,
        None if status.session_cost_usd is None else f"${status.session_cost_usd:.2f}",
    ]
    return _SEPARATOR.join(block for block in blocks if block)


def render_job_usage(job: str, turns: int, tokens: int, cost_usd: float) -> str:
    """Render a job's cumulative usage as an indented status-line footer row.

    The turns/tokens are shown only when the job has been deep-metered (``turns``
    > 0); the job's cost always shows. The leading indent sets it apart from the
    live status line above it.

    Args:
        job: The job identifier.
        turns: The job's recorded turn count across sessions (``0`` if unmetered).
        tokens: The job's total tokens across turns (input + output + cache).
        cost_usd: The job's cumulative cost across its sessions.

    Returns:
        The footer row (no trailing newline).
    """
    parts = [f"job {job}"]
    if turns:
        parts.append(f"{turns} turns")
        parts.append(f"{tokens} tok")
    parts.append(f"${cost_usd:.2f}")
    return "  " + " · ".join(parts)


def _git(workspace: Workspace) -> str | None:
    if workspace.branch is None:
        return None
    head = f"{workspace.repo}/{workspace.branch}" if workspace.repo else workspace.branch
    parts = [f"git {head}"]
    if workspace.short_sha:
        parts.append(workspace.short_sha)
    if workspace.dirty:
        parts.append(f"dirty:{workspace.dirty}")
    return " ".join(parts)


def _folder(workspace: Workspace) -> str | None:
    return None if workspace.folder is None else f"📁 {workspace.folder}"
