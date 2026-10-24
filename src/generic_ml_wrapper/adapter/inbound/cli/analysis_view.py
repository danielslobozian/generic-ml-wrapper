# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Render a session analysis as text, in the status line's units and marks."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.service.statusline_renderer import (
    format_age,
    render_tokens,
    render_tools,
)
from generic_ml_wrapper.common import i18n

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.session_analysis import (
        DurationStats,
        SessionAnalysis,
    )

_MINUTE = 60.0


def format_analysis(analysis: SessionAnalysis, loc: i18n.Localizer | None = None) -> str:
    """One session's figures, a line each.

    Args:
        analysis: The session's figures.
        loc: The localiser to render through; defaults to the active language.

    Returns:
        The text to print (no trailing newline).
    """
    loc = loc or i18n.active()
    lines = [
        loc.t("analyze.title", session=analysis.session_id, client=analysis.client)
        if analysis.session_id is not None
        else loc.t("analyze.title_outside", client=analysis.client),
        loc.t("analyze.file", path=_home_relative(analysis.source)),
    ]
    if analysis.started_at is not None and analysis.ended_at is not None:
        lines.append(
            loc.t(
                "analyze.span",
                start=_when(analysis.started_at),
                end=_when(analysis.ended_at),
                length=format_age(analysis.ended_at - analysis.started_at),
            )
        )
    lines += [
        loc.t("analyze.models", models=", ".join(analysis.models) or loc.t("analyze.unknown")),
        loc.t(
            "analyze.turns",
            turns=analysis.main_turns + analysis.agent_turns,
            main=analysis.main_turns,
            agents=analysis.agent_turns,
            prompts=analysis.prompts,
        ),
        loc.t("analyze.tokens", tokens=render_tokens(analysis.tokens)),
        _answers(analysis.answer_times, loc),
        loc.t("analyze.tools", tools=render_tools(analysis.tools))
        if analysis.tools.total
        else loc.t("analyze.tools_none"),
    ]
    lines += [
        loc.t(
            "analyze.tool_time",
            name=timing.name,
            median=format_duration(timing.durations.median),
            max=format_duration(timing.durations.maximum),
            count=timing.durations.count,
        )
        for timing in analysis.tool_times
    ]
    if analysis.tool_times:
        lines.append(loc.t("analyze.tool_time_note"))
    return "\n".join(lines)


def format_duration(seconds: float) -> str:
    """A duration short enough to scan: ``0.4s``, ``12s``, then ``3m``, ``1h05m``.

    Under a minute it keeps a tenth of a second while that still says something (a tool
    call is often a fraction of a second); from a minute on it is the status line's age.
    """
    if seconds < _MINUTE:
        rounded = f"{seconds:.1f}" if seconds < 10 else f"{seconds:.0f}"  # noqa: PLR2004
        return f"{rounded.removesuffix('.0')}s"
    return format_age(seconds)


def _answers(times: DurationStats | None, loc: i18n.Localizer) -> str:
    """The prompt-to-answer spread, or that no answer finished."""
    if times is None:
        return loc.t("analyze.answers_none")
    return loc.t(
        "analyze.answers",
        min=format_duration(times.minimum),
        median=format_duration(times.median),
        avg=format_duration(times.mean),
        max=format_duration(times.maximum),
    )


def _when(timestamp: float) -> str:
    """An epoch timestamp as a local ``YYYY-MM-DD HH:MM``."""
    return datetime.fromtimestamp(timestamp).astimezone().strftime("%Y-%m-%d %H:%M")


def _home_relative(source: str) -> str:
    """``source`` with the home folder written ``~``, as the status line writes folders."""
    path = Path(source)
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return source
