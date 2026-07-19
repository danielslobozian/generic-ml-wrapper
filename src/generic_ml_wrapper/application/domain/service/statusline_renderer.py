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
        _context(status),
        *status.extras,
        None if status.session_cost_usd is None else f"${status.session_cost_usd:.2f}",
    ]
    return _SEPARATOR.join(block for block in blocks if block)


def _context(status: ClientStatus) -> str | None:
    """The context-fill block: ``ctx 155.6k/200k (78%)``, degrading to ``ctx 78%``.

    Shows the denominator when the client reports both the tokens in the window and
    the window size -- a bare percentage hides whether the window is 200k or 1M. When
    either is missing, falls back to the percentage alone; when even that is absent,
    the block is omitted.
    """
    pct = status.context_pct
    if status.context_tokens is not None and status.context_window_size:
        computed = round(100 * status.context_tokens / status.context_window_size)
        shown = pct if pct is not None else computed
        return (
            f"ctx {_compact(status.context_tokens)}/"
            f"{_compact(status.context_window_size)} ({shown}%)"
        )
    return None if pct is None else f"ctx {pct}%"


_MILLION = 1_000_000
_THOUSAND = 1_000


def _compact(tokens: int) -> str:
    """A compact token count: ``200000`` -> ``200k``, ``1000000`` -> ``1M``."""
    if tokens >= _MILLION:
        return _trim(tokens / _MILLION) + "M"
    if tokens >= _THOUSAND:
        return _trim(tokens / _THOUSAND) + "k"
    return str(tokens)


def _trim(value: float) -> str:
    """One decimal place, with a trailing ``.0`` dropped (``200.0`` -> ``200``)."""
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def render_usage_row(label: str, name: str, turns: int, tokens: int, cost_usd: float) -> str:
    """Render one usage footer row -- ``<label> <name> · N turns · tok · $`` -- indented.

    Used for both the current-session row (``label="session"``) and the whole-job
    total (``label="job"``). Turns/tokens show only when deep-metered (``turns`` > 0);
    the cost always shows. The leading indent sets the footer apart from the live line.

    Args:
        label: The scope label, ``"session"`` or ``"job"``.
        name: The session id or job id.
        turns: The recorded turn count for this scope (``0`` if unmetered).
        tokens: The total tokens across those turns (input + output + cache).
        cost_usd: The scope's cumulative cost.

    Returns:
        The footer row (no trailing newline).
    """
    parts = [f"{label} {name}"]
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
