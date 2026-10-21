# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Pure rendering of the working environment and client status into one line."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.context_thresholds import ContextLevel
from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.agent_usage import AgentUsage
    from generic_ml_wrapper.application.domain.model.client_status import ClientStatus
    from generic_ml_wrapper.application.domain.model.context_thresholds import (
        ContextThresholds,
    )
    from generic_ml_wrapper.application.domain.model.tool_calls import ToolCalls
    from generic_ml_wrapper.application.domain.model.workspace import Workspace

_SEPARATOR = "  ·  "
# The ANSI colours of a worrying context: yellow, then red. A client that renders the
# status line in a terminal shows them; ``NO_COLOR`` or ``[statusline] color`` turn them off.
_PAINT = {ContextLevel.WARN: "\033[33m", ContextLevel.ALERT: "\033[31m"}
_RESET = "\033[0m"


def render_statusline(
    status: ClientStatus, workspace: Workspace, thresholds: ContextThresholds | None = None
) -> str:
    """Render the working environment and client status as a single line.

    The wrapper's own facts (git, folder) come first, then the common client
    fields (model, context), then any client-specific ``extras`` (already
    formatted, e.g. Claude's quota), then cost. Blocks the environment or client
    did not provide are omitted, so a bare environment with an empty status yields
    an empty line.

    Args:
        status: The parsed client status.
        workspace: The working environment the wrapper computed.
        thresholds: When to colour the context block yellow, then red; ``None`` leaves
            it uncoloured.

    Returns:
        The status line (no trailing newline).
    """
    blocks = [
        _git(workspace),
        _folder(workspace),
        status.model,
        _painted(_context(status), status, thresholds),
        *status.extras,
        None if status.session_cost_usd is None else f"${status.session_cost_usd:.2f}",
    ]
    return _SEPARATOR.join(block for block in blocks if block)


def _painted(
    block: str | None, status: ClientStatus, thresholds: ContextThresholds | None
) -> str | None:
    """``block`` in the colour its context's level calls for, when there is one."""
    if block is None or thresholds is None:
        return block
    colour = _PAINT.get(thresholds.level(status))
    return block if colour is None else f"{colour}{block}{_RESET}"


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


_MINUTE = 60
_HOUR = 3600
_DAY = 86400

_BILLION = 1_000_000_000
_MILLION = 1_000_000
_THOUSAND = 1_000


def _compact(tokens: int) -> str:
    """A compact token count in SI units: ``200000`` -> ``200k``, ``1.2e9`` -> ``1.2G``.

    Scales through ``k`` (thousand), ``M`` (million), ``G`` (billion) so a heavy job's
    cache-dominated total stays scannable instead of a ten-digit run. Below 1000 the raw
    count is exact.
    """
    if tokens >= _BILLION:
        return _trim(tokens / _BILLION) + "G"
    if tokens >= _MILLION:
        return _trim(tokens / _MILLION) + "M"
    if tokens >= _THOUSAND:
        return _trim(tokens / _THOUSAND) + "k"
    return str(tokens)


def _trim(value: float) -> str:
    """One decimal place, with a trailing ``.0`` dropped (``200.0`` -> ``200``)."""
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def format_age(seconds: float) -> str:
    """Render an elapsed time as two significant units: ``5d``, ``1d20h``, ``2h45m``.

    Two units rather than one because the coarse form loses the half a session is
    usually made of -- ``2h`` reads the same at two hours and at two hours fifty-nine.
    The second unit is dropped when it is zero, so a round duration stays short.

    Deliberately separate from the parser's own single-unit duration, which renders a
    quota reset marker where a glance ("about an hour") is all that is wanted.

    Args:
        seconds: The elapsed seconds; negative values are treated as zero.

    Returns:
        The compact duration (``45s`` at the shortest).
    """
    whole = int(max(seconds, 0))
    days, whole = divmod(whole, _DAY)
    hours, whole = divmod(whole, _HOUR)
    minutes, whole = divmod(whole, _MINUTE)
    if days:
        return f"{days}d{hours}h" if hours else f"{days}d"
    if hours:
        return f"{hours}h{minutes:02d}m" if minutes else f"{hours}h"
    return f"{minutes}m" if minutes else f"{whole}s"


def render_usage_row(  # noqa: PLR0913, PLR0917  (one row's worth of fields)
    label: str,
    name: str,
    turns: int,
    tokens: TokenCounts,
    cost_usd: float,
    age_s: float | None = None,
    agents: AgentUsage | None = None,
    *,
    tools: ToolCalls | None = None,
) -> str:
    """Render one usage footer row -- ``<label> <name> (age) · N turns · ↑ ↓ ⟲ ✎ · ⚒ · $``.

    Used for both the current-session row (``label="session"``) and the whole-job
    total (``label="job"``). Turns/tokens show only when deep-metered (``turns`` > 0);
    the cost always shows. The leading indent sets the footer apart from the live line.

    The age is bound to the name in parentheses rather than added as another
    ``·``-separated field: the separators read as a list of measurements -- turns,
    tokens, dollars -- and how old the thing is is a property of it, not one more
    measurement to scan past.

    Args:
        label: The scope label, ``"session"`` or ``"job"``.
        name: The session id or job id.
        turns: The recorded turn count for this scope (``0`` if unmetered).
        tokens: The tokens across those turns, by kind -- shown as ``↑`` input, ``↓``
            output, ``⟲`` cache read and ``✎`` cache write, each compacted to k/M/G.
        cost_usd: The scope's cumulative cost.
        age_s: How long ago this scope's first recorded turn was, or ``None`` when it
            has none -- a session launched but never prompted has no age to show.
        agents: The agents' (subagents') part of ``turns`` and ``tokens``, or ``None``
            when they had none; the turn count and each kind then show their share.
        tools: The tools those turns called, or ``None``; shown as their total and the
            most called (``⚒ 48 (Bash 30, Read 12, WebSearch 6, …)``) once there is one.

    Returns:
        The footer row (no trailing newline).
    """
    head = f"{label} {name}" if age_s is None else f"{label} {name} ({format_age(age_s)})"
    parts = [head]
    if turns:
        own, caused = (0, 0) if agents is None else (agents.turns, agents.caused_turns)
        parts.append(f"{turns} turns{_shares(own, caused, turns)}")
        parts.append(render_tokens(tokens, agents))
        if tools is not None and tools.total:
            parts.append(render_tools(tools))
    parts.append(f"${cost_usd:.2f}")
    return "  " + " · ".join(parts)


def render_tokens(tokens: TokenCounts, agents: AgentUsage | None = None) -> str:
    """The four token counts as ``↑ 182k  ↓ 96k  ⟲ 8.6M  ✎ 240k``.

    A space after each mark, so a narrow glyph never runs into its number; two between
    the pairs, so each reads as one unit. Compacted to k/M/G, because the cache read of
    a long session runs to millions and must stay scannable.

    With ``agents``, each kind the agents used is followed by their share of it --
    ``⟲ 8.6M (60%)`` -- the total staying the first number read. A share is a
    percentage rather than a count: it answers "how much of this was the agents" at a
    glance, and it is the same width whatever the unit. The share of the main turns
    they caused follows it with a ``+``: ``⟲ 8.6M (60% +25%)``.
    """
    own = TokenCounts() if agents is None else agents.tokens
    caused = TokenCounts() if agents is None else agents.caused_tokens
    pairs = (
        ("↑", tokens.input, own.input, caused.input),
        ("↓", tokens.output, own.output, caused.output),
        ("⟲", tokens.cache_read, own.cache_read, caused.cache_read),
        ("✎", tokens.cache_write, own.cache_write, caused.cache_write),
    )
    return "  ".join(
        f"{mark} {_compact(count)}{_shares(part, extra, count)}"
        for mark, count, part, extra in pairs
    )


# How many tools the status line names; the rest are only in the total and the export.
_TOP_TOOLS = 3


def render_tools(tools: ToolCalls) -> str:
    """The tool calls as their total, then the most called: ``⚒ 48 (Bash 30, Read 12, …)``.

    Commas inside the parenthesis, because the row's own ``·`` separates its fields.
    """
    named = [f"{name} {_compact(calls)}" for name, calls in tools.counts[:_TOP_TOOLS]]
    if len(tools.counts) > _TOP_TOOLS:
        named.append("…")
    return f"⚒ {_compact(tools.total)} ({', '.join(named)})"


def _shares(own: int, caused: int, whole: int) -> str:
    """`` (60% +25%)``: the agents' own share of ``whole``, then the one they caused.

    Each is left out when it is nothing, and the parenthesis too when both are.
    """
    shares = [_share(own, whole)] if own else []
    if caused:
        shares.append(f"+{_share(caused, whole)}")
    return f" ({' '.join(shares)})" if shares else ""


def _share(part: int, whole: int) -> str:
    """``part`` as a whole percentage of ``whole``.

    Never ``0%`` for a part that is there, and never ``100%`` for one that is not all of it.
    """
    percent = round(part * 100 / whole)
    if percent < 1:
        return "<1%"
    if percent >= 100 and part < whole:  # noqa: PLR2004  (a percentage's ceiling)
        return "99%"
    return f"{percent}%"


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
