# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Pure rendering of the working environment and client status into one line."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.context_thresholds import ContextLevel
from generic_ml_wrapper.application.domain.model.statusline_layout import (
    TOKEN_FIELDS,
    StatuslineLayout,
)
from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

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
# The full status line, every block in its default place.
_FULL = StatuslineLayout()


def render_statusline(
    status: ClientStatus,
    workspace: Workspace,
    thresholds: ContextThresholds | None = None,
    layout: StatuslineLayout = _FULL,
) -> str:
    """Render the working environment and client status as a single line.

    The client's fields lead -- model, context, any client-specific ``extras``
    (already formatted, e.g. Claude's quota), then cost -- and the wrapper's own
    facts (git, folder) close the line, so what is spent is read before where the
    work happens. Blocks the environment or client did not provide are omitted, so a
    bare environment with an empty status yields an empty line. ``layout`` can hide
    blocks and reorder them.

    Args:
        status: The parsed client status.
        workspace: The working environment the wrapper computed.
        thresholds: When to colour the context block yellow, then red; ``None`` leaves
            it uncoloured.
        layout: The blocks to show, in order (see :class:`StatuslineLayout`).

    Returns:
        The status line (no trailing newline).
    """
    blocks: dict[str, tuple[str | None, ...]] = {
        "model": (status.model,),
        "context": (_painted(_context(status), status, thresholds),),
        "quota": status.extras,
        "cost": (None if status.session_cost_usd is None else f"${status.session_cost_usd:.2f}",),
        "git": (_git(workspace),),
        "folder": (_folder(workspace),),
    }
    shown = [block for name in layout.line for block in blocks[name]]
    return _SEPARATOR.join(block for block in shown if block)


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
    label_width: int = 0,
    head_width: int = 0,
    layout: StatuslineLayout = _FULL,
) -> str:
    """Render one usage footer row -- ``<label> <name> (age) · $ · N turns · ↑ ↓ ⟲ ✎ · ⚒``.

    Used for both the current-session row (``label="session"``) and the whole-job
    total (``label="job"``). Turns/tokens show only when deep-metered (``turns`` > 0);
    the cost always shows, right after the name, so it is read first. The leading indent
    sets the footer apart from the live line.

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
        label_width: The width the label is padded to, so stacked rows start their names
            in one column; ``0`` pads nothing.
        head_width: The width the ``<label> <name> (age)`` head is padded to, so stacked
            rows line up their ``·`` fields (see :func:`usage_row_head`); ``0`` pads nothing.
        layout: The fields to show, in order, and those followed by the agents' share
            (see :class:`StatuslineLayout`). Token kinds next to each other share one
            ``·`` field.

    Returns:
        The footer row (no trailing newline).
    """
    parts = [usage_row_head(label, name, age_s, label_width).ljust(head_width)]
    kinds: list[str] = []  # the run of adjacent token kinds being gathered into one field
    for field in (*layout.rows, ""):  # the sentinel flushes a trailing run of kinds
        if field in TOKEN_FIELDS:
            kinds.append(field)
            continue
        if kinds and turns:
            parts.append(render_tokens(tokens, agents, kinds, layout.agents))
        kinds = []
        if field == "cost":
            parts.append(f"${cost_usd:.2f}")
        elif field == "turns" and turns:
            share = agents if "turns" in layout.agents else None
            own, caused = (0, 0) if share is None else (share.turns, share.caused_turns)
            parts.append(f"{turns} turns{_shares(own, caused, turns)}")
        elif field == "tools" and turns and tools is not None and tools.total:
            parts.append(render_tools(tools))
    return "  " + " · ".join(parts)


def usage_row_head(label: str, name: str, age_s: float | None = None, label_width: int = 0) -> str:
    """A footer row's head, ``<label> <name> (age)``, with the label padded to ``label_width``.

    Exposed so whoever stacks rows can measure the widest head and pass it back as
    ``head_width``.
    """
    head = f"{label.ljust(label_width)} {name}"
    return head if age_s is None else f"{head} ({format_age(age_s)})"


def render_tokens(
    tokens: TokenCounts,
    agents: AgentUsage | None = None,
    kinds: Sequence[str] = TOKEN_FIELDS,
    agent_kinds: Collection[str] = TOKEN_FIELDS,
) -> str:
    """The four token counts as ``↑ 182k  ↓ 96k  ⟲ 8.6M  ✎ 240k``.

    A space after each mark, so a narrow glyph never runs into its number; two between
    the pairs, so each reads as one unit. Compacted to k/M/G, because the cache read of
    a long session runs to millions and must stay scannable.

    With ``agents``, each kind the agents used is followed by their share of it --
    ``⟲ 8.6M (60%)`` -- the total staying the first number read. A share is a
    percentage rather than a count: it answers "how much of this was the agents" at a
    glance, and it is the same width whatever the unit. The share of the main turns
    they caused follows it with a ``+``: ``⟲ 8.6M (60% +25%)``.

    ``kinds`` picks the kinds shown and their order (``input``, ``output``,
    ``cache_read``, ``cache_write``); only those also in ``agent_kinds`` show the share.
    """
    own = TokenCounts() if agents is None else agents.tokens
    caused = TokenCounts() if agents is None else agents.caused_tokens
    pairs = {
        "input": ("↑", tokens.input, own.input, caused.input),
        "output": ("↓", tokens.output, own.output, caused.output),
        "cache_read": ("⟲", tokens.cache_read, own.cache_read, caused.cache_read),
        "cache_write": ("✎", tokens.cache_write, own.cache_write, caused.cache_write),
    }
    rendered: list[str] = []
    for kind in kinds:
        mark, count, part, extra = pairs[kind]
        share = _shares(part, extra, count) if kind in agent_kinds else ""
        rendered.append(f"{mark} {_compact(count)}{share}")
    return "  ".join(rendered)


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
