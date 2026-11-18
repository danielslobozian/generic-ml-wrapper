# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""A job's usage report, rendered for reading: a totals line and one table per grouping.

The JSON export keeps raw integers for tools; this is the people's side of the same
report -- token counts in k/M/G, durations in minutes and hours, shares as percentages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model.turn_origin import TurnRole
from generic_ml_wrapper.application.domain.service.statusline_renderer import (
    compact,
    format_age,
)
from generic_ml_wrapper.common import i18n

if TYPE_CHECKING:
    from collections.abc import Iterable

    from generic_ml_wrapper.application.port.inbound.export_usage import (
        AgentTotal,
        ModelTotal,
        SessionTotal,
        UsageReport,
    )

#: One table: its tab title, its column heads, and its rows of cells.
Table = tuple[str, tuple[str, ...], tuple[tuple[str, ...], ...]]


def usage_tables(
    report: UsageReport, loc: i18n.Localizer | None = None
) -> tuple[str, tuple[Table, ...]]:
    """The report's totals line and its tables: by model, agent (if any), tool, session.

    Args:
        report: The job's usage report.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        ``(summary, tables)``. A grouping with nothing in it has no table.
    """
    loc = loc or i18n.active()
    whole = _all_tokens(report)
    tables = (
        _counted_table(
            loc.t("export.tab.model"),
            loc.t("export.col.model"),
            ((model.model, model) for model in report.models),
            whole,
            loc,
        ),
        _counted_table(
            loc.t("export.tab.agent"),
            loc.t("export.col.agent"),
            ((_side(agent, loc), agent) for agent in report.agents),
            whole,
            loc,
        ),
        _tool_table(report, loc),
        _session_table(report, whole, loc),
    )
    return _summary(report, whole, loc), tuple(table for table in tables if table[2])


def _summary(report: UsageReport, whole: int, loc: i18n.Localizer) -> str:
    """``412 turns · 1h12m · ↑ 1.2M  ↓ 340k  ⟲ 12.4M  ✎ 800k · agents 38% · $8.40``."""
    agents = sum(_all_tokens(agent) for agent in report.agents if agent.role is TurnRole.AGENT)
    parts = [
        loc.t("usage.view.turns", count=report.turn_count),
        format_age(report.duration_s),
        loc.t(
            "usage.view.tokens",
            input=compact(report.input_tokens),
            output=compact(report.output_tokens),
            cache_read=compact(report.cache_read_tokens),
            cache_write=compact(report.cache_write_tokens),
        ),
    ]
    if agents:
        parts.append(loc.t("usage.view.agents", share=_share(agents, whole)))
    parts.append(f"${report.total_usd:.2f}")
    return " · ".join(parts)


def _tool_table(report: UsageReport, loc: i18n.Localizer) -> Table:
    """Calls by tool, and each tool's share of all the calls."""
    calls = sum(tool.calls for tool in report.tools)
    return (
        loc.t("export.tab.tool"),
        (loc.t("export.col.tool"), loc.t("export.col.calls"), loc.t("export.col.share")),
        tuple((tool.tool, str(tool.calls), _share(tool.calls, calls)) for tool in report.tools),
    )


def _session_table(report: UsageReport, whole: int, loc: i18n.Localizer) -> Table:
    """The token table by session, with the cost its client reported (``-`` when none)."""
    title, columns, rows = _counted_table(
        loc.t("export.tab.session"),
        loc.t("export.col.session"),
        ((session.session_id, session) for session in report.sessions),
        whole,
        loc,
    )
    costs = (
        "-" if session.cost_usd is None else f"${session.cost_usd:.2f}"
        for session in report.sessions
    )
    return (
        title,
        (*columns, loc.t("export.col.cost")),
        tuple((*row, cost) for row, cost in zip(rows, costs, strict=True)),
    )


def _counted_table(
    title: str,
    name: str,
    totals: Iterable[tuple[str, ModelTotal | AgentTotal | SessionTotal]],
    whole: int,
    loc: i18n.Localizer,
) -> Table:
    """A table of token totals: name, calls, the four kinds, share of all tokens, duration."""
    columns = (
        name,
        loc.t("export.col.calls"),
        loc.t("export.col.input"),
        loc.t("export.col.output"),
        loc.t("export.col.cache_write"),
        loc.t("export.col.cache_read"),
        loc.t("export.col.share"),
        loc.t("export.col.duration"),
    )
    rows = tuple(
        (
            label,
            str(total.calls),
            compact(total.input_tokens),
            compact(total.output_tokens),
            compact(total.cache_write_tokens),
            compact(total.cache_read_tokens),
            _share(_all_tokens(total), whole),
            format_age(total.duration_s),
        )
        for label, total in totals
    )
    return title, columns, rows


def _all_tokens(total: ModelTotal | AgentTotal | SessionTotal | UsageReport) -> int:
    return (
        total.input_tokens
        + total.output_tokens
        + total.cache_read_tokens
        + total.cache_write_tokens
    )


def _share(part: int, whole: int) -> str:
    """``part`` as a percentage of ``whole``; ``<1%`` for a part that is there but small."""
    if not whole:
        return "-"
    percent = round(part * 100 / whole)
    return "<1%" if part and percent < 1 else f"{percent}%"


def _side(agent: AgentTotal, loc: i18n.Localizer) -> str:
    """The main conversation, its turns the agents caused, or the agent by name."""
    if agent.agent is not None:
        return agent.agent
    if agent.role is TurnRole.AGENT:
        return loc.t("usage.role_agent")
    return loc.t("usage.role_main_caused" if agent.caused_by_agent else "usage.role_main")
