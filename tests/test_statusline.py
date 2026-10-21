# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for status parsing, rendering, and the RenderStatusline use case."""

import json

import pytest

from generic_ml_wrapper.adapter.outbound.status.claude_status_parser import ClaudeStatusParser
from generic_ml_wrapper.application.domain.model.agent_usage import AgentUsage
from generic_ml_wrapper.application.domain.model.client_status import ClientStatus
from generic_ml_wrapper.application.domain.model.context_thresholds import (
    ContextLevel,
    ContextThresholds,
)
from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts
from generic_ml_wrapper.application.domain.model.tool_calls import ToolCalls
from generic_ml_wrapper.application.domain.model.turn_origin import TurnRole
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.domain.model.workspace import Workspace
from generic_ml_wrapper.application.domain.service.statusline_renderer import (
    format_age,
    render_statusline,
    render_tokens,
    render_usage_row,
)
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort
from generic_ml_wrapper.application.port.outbound.workspace import WorkspaceInspectorPort
from generic_ml_wrapper.application.usecase.render_statusline import RenderStatuslineUseCase
from generic_ml_wrapper.application.wiring import composition

_NOW = 1_000_000.0
_CLAUDE_PAYLOAD: dict[str, object] = {
    "model": {"display_name": "Opus 4.8"},
    "context_window": {
        "used_percentage": 34,
        "context_window_size": 200000,
        "total_input_tokens": 68000,
    },
    "cost": {"total_cost_usd": 0.4321},
    "rate_limits": {
        "five_hour": {"used_percentage": 12, "resets_at": _NOW + 12 * 60},
        "seven_day": {"used_percentage": 47, "resets_at": _NOW + 3 * 86400},
    },
}


def _clock() -> float:
    return _NOW


_NO_WORKSPACE = Workspace(folder=None, repo=None, branch=None, short_sha=None, dirty=0)
_REPO = Workspace(folder="~/dev/app", repo="app", branch="main", short_sha="abc1234", dirty=3)


class FakeUsageStore(UsageStorePort):
    def __init__(self) -> None:
        self.recorded: list[tuple[str, str, float]] = []

    def record_session_cost(self, job: str, session: str, cost_usd: float) -> None:
        self.recorded.append((job, session, cost_usd))

    def session_costs(self, job: str) -> dict[str, float]:
        return {}


class FakePerTurnStore(PerTurnMeteringPort):
    def __init__(self, turns: list[TurnUsage] | None = None) -> None:
        self._turns = turns or []

    def record(self, job: str, turn: TurnUsage) -> None:
        raise NotImplementedError

    def turns_for_job(self, job: str) -> list[TurnUsage]:
        return self._turns


class FakeWorkspaceInspector(WorkspaceInspectorPort):
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def inspect(self) -> Workspace:
        return self.workspace


def _status(**overrides: object) -> ClientStatus:
    fields: dict[str, object] = {
        "model": None,
        "context_pct": None,
        "session_cost_usd": None,
        "extras": (),
    }
    fields.update(overrides)
    return ClientStatus(**fields)  # type: ignore[arg-type]


# ── parser ──
def test_claude_parser_reads_the_fields() -> None:
    status = ClaudeStatusParser(clock=_clock).parse(_CLAUDE_PAYLOAD)
    assert status.model == "Opus 4.8"
    assert status.context_pct == 34
    assert status.context_window_size == 200000
    assert status.context_tokens == 68000
    assert status.session_cost_usd == 0.4321
    assert status.extras == ("quota 5h 12% (↻ 12m) · wk 47% (↻ 3d)",)


def test_claude_parser_reads_partial_quota() -> None:
    # No resets_at → the window renders as percentage only (reset marker omitted).
    status = ClaudeStatusParser().parse({"rate_limits": {"five_hour": {"used_percentage": 80}}})
    assert status.extras == ("quota 5h 80%",)


def test_claude_parser_reset_durations() -> None:
    parser = ClaudeStatusParser(clock=_clock)

    def extras_at(delta: float) -> tuple[str, ...]:
        payload: dict[str, object] = {
            "rate_limits": {"five_hour": {"used_percentage": 5, "resets_at": _NOW + delta}}
        }
        return parser.parse(payload).extras

    assert extras_at(30) == ("quota 5h 5% (↻ 0m)",)  # under a minute
    assert extras_at(90) == ("quota 5h 5% (↻ 1m)",)
    assert extras_at(2 * 3600) == ("quota 5h 5% (↻ 2h)",)
    assert extras_at(5 * 86400) == ("quota 5h 5% (↻ 5d)",)
    assert extras_at(-100) == ("quota 5h 5% (↻ 0m)",)  # already past → 0m


def test_claude_parser_tolerates_missing_fields() -> None:
    parsed = ClaudeStatusParser().parse({})
    assert parsed == _status()
    assert parsed.extras == ()


# ── renderer ──
def test_render_omits_missing_fields() -> None:
    assert render_statusline(_status(), _NO_WORKSPACE) == ""
    assert render_statusline(_status(model="Opus 4.8"), _NO_WORKSPACE) == "Opus 4.8"


def test_render_context_shows_denominator() -> None:
    status = _status(context_pct=34, context_tokens=68000, context_window_size=200000)
    assert render_statusline(status, _NO_WORKSPACE) == "ctx 68k/200k (34%)"


def test_render_context_compact_and_computes_pct_when_absent() -> None:
    # 1M window, fractional-k tokens; percentage computed since the client omitted it.
    status = _status(context_tokens=155615, context_window_size=1_000_000)
    assert render_statusline(status, _NO_WORKSPACE) == "ctx 155.6k/1M (16%)"


def test_render_context_falls_back_to_pct_without_tokens_or_size() -> None:
    assert render_statusline(_status(context_pct=34), _NO_WORKSPACE) == "ctx 34%"


def test_render_full_line() -> None:
    status = _status(
        model="Opus 4.8", context_pct=34, extras=("quota 5h 12% · wk 47%",), session_cost_usd=0.43
    )
    line = render_statusline(status, _REPO)
    assert "git app/main abc1234 dirty:3" in line
    assert "📁 ~/dev/app" in line
    assert "Opus 4.8" in line
    assert "ctx 34%" in line
    assert "quota 5h 12% · wk 47%" in line
    assert "$0.43" in line


def test_render_places_extras_between_context_and_cost() -> None:
    status = _status(context_pct=34, extras=("quota 5h 12%", "plan auto 8%"), session_cost_usd=0.43)
    line = render_statusline(status, _NO_WORKSPACE)
    assert line == "ctx 34%  ·  quota 5h 12%  ·  plan auto 8%  ·  $0.43"


def test_render_git_omits_sha_and_dirty_when_clean() -> None:
    clean = Workspace(folder=None, repo="app", branch="main", short_sha=None, dirty=0)
    assert render_statusline(_status(), clean) == "git app/main"


def test_render_git_without_repo_name() -> None:
    detached = Workspace(folder=None, repo=None, branch="wip", short_sha=None, dirty=0)
    assert render_statusline(_status(), detached) == "git wip"


# ── usage footer rows ──
_TOKENS = TokenCounts(input=182_000, output=96_400, cache_read=8_600_000, cache_write=240_000)


def test_render_usage_row_with_turns() -> None:
    assert (
        render_usage_row("job", "JOB-1", 3, _TOKENS, 0.43)
        == "  job JOB-1 · 3 turns · ↑ 182k  ↓ 96.4k  ⟲ 8.6M  ✎ 240k · $0.43"
    )


def test_each_token_count_compacts_to_k_m_g() -> None:
    # A long session's cache read runs to millions and must stay scannable.
    assert render_tokens(TokenCounts(999, 45_194, 487_000_000, 8_472_936_150)) == (
        "↑ 999  ↓ 45.2k  ⟲ 487M  ✎ 8.5G"
    )


def test_each_kind_the_agents_used_shows_their_share() -> None:
    tokens = TokenCounts(182_000, 96_000, 8_600_000, 240_000)
    agents = AgentUsage(tokens=TokenCounts(40_000, 0, 5_160_000, 240_000))
    # output untouched by agents: no parenthesis; cache write all theirs: 100%
    assert render_tokens(tokens, agents) == ("↑ 182k (22%)  ↓ 96k  ⟲ 8.6M (60%)  ✎ 240k (100%)")


@pytest.mark.parametrize(
    ("part", "whole", "share"),
    [
        (1, 1_000, "<1%"),  # there, but under a percent: never shown as 0%
        (995, 1_000, "99%"),  # not all of it: never rounded up to 100%
        (1_000, 1_000, "100%"),
        (505, 1_000, "50%"),
    ],
)
def test_a_share_is_a_whole_percentage_that_never_misleads(
    part: int, whole: int, share: str
) -> None:
    assert render_tokens(TokenCounts(input=whole), AgentUsage(tokens=TokenCounts(input=part))) == (
        f"↑ 1k ({share})  ↓ 0  ⟲ 0  ✎ 0"
    )


def test_the_agents_share_of_the_turns_follows_the_turn_count() -> None:
    row = render_usage_row("job", "JOB-1", 412, _TOKENS, 0.43, agents=AgentUsage(292, _TOKENS))
    assert row.startswith("  job JOB-1 · 412 turns (71%) · ")


def test_no_agent_turns_leaves_the_turn_count_bare() -> None:
    row = render_usage_row("job", "JOB-1", 3, _TOKENS, 0.43)
    assert " · 3 turns · " in row


def test_the_main_turns_the_agents_caused_follow_their_own_share() -> None:
    tokens = TokenCounts(182_000, 96_000, 8_600_000, 240_000)
    agents = AgentUsage(
        60, TokenCounts(40_000, 0, 5_160_000, 0), 10, TokenCounts(9_100, 2_880, 2_150_000, 0)
    )
    row = render_usage_row("session", "PAY-1_003", 86, tokens, 2.5, agents=agents)
    # output untouched by the agents themselves: only what they caused
    assert row == (
        "  session PAY-1_003 · 86 turns (70% +12%) · "
        "↑ 182k (22% +5%)  ↓ 96k (+3%)  ⟲ 8.6M (60% +25%)  ✎ 240k · $2.50"
    )


def test_render_usage_row_without_turns_shows_only_cost() -> None:
    assert render_usage_row("job", "JOB-1", 0, TokenCounts(), 0.43) == "  job JOB-1 · $0.43"


def test_render_usage_row_session_label() -> None:
    assert (
        render_usage_row("session", "JOB-1_002", 2, TokenCounts(80, 20), 0.10)
        == "  session JOB-1_002 · 2 turns · ↑ 80  ↓ 20  ⟲ 0  ✎ 0 · $0.10"
    )


# ── use case ──
def _use_case(
    usage: FakeUsageStore,
    workspace: Workspace,
    turns: FakePerTurnStore | None = None,
    now: float = 0.0,
) -> RenderStatuslineUseCase:
    return RenderStatuslineUseCase(
        ClaudeStatusParser(clock=_clock),
        usage,
        FakeWorkspaceInspector(workspace),
        turns or FakePerTurnStore(),
        clock=lambda: now,
    )


def test_use_case_records_cost_and_renders() -> None:
    usage = FakeUsageStore()
    line = _use_case(usage, _REPO).execute(json.dumps(_CLAUDE_PAYLOAD), "JOB-1", "JOB-1_001")
    assert "$0.43" in line
    assert "git app/main" in line
    assert usage.recorded == [("JOB-1", "JOB-1_001", 0.4321)]


def test_use_case_shows_only_the_session_row_for_a_single_session() -> None:
    turns = FakePerTurnStore(
        [
            TurnUsage(
                "JOB-1_001", 3106, 7, None, "m", cache_creation_tokens=42081, cache_read_tokens=0
            )
        ]
    )
    out = _use_case(FakeUsageStore(), _NO_WORKSPACE, turns).execute("{}", "JOB-1", "JOB-1_001")
    # one session → just the current-session row (no separate job total)
    assert out == "  session JOB-1_001 · 1 turns · ↑ 3.1k  ↓ 7  ⟲ 0  ✎ 42.1k · $0.00"


def test_use_case_shows_session_then_job_row_across_sessions() -> None:
    turns = FakePerTurnStore(
        [
            TurnUsage("JOB-1_001", 100, 20, None, "m"),  # a prior session
            TurnUsage("JOB-1_002", 300, 40, None, "m"),  # the current session
            TurnUsage("JOB-1_002", 10, 5, None, "m"),
        ]
    )
    out = _use_case(FakeUsageStore(), _NO_WORKSPACE, turns).execute("{}", "JOB-1", "JOB-1_002")
    # current session first, then the job total across both sessions
    assert out == (
        "  session JOB-1_002 · 2 turns · ↑ 310  ↓ 45  ⟲ 0  ✎ 0 · $0.00\n"
        "  job JOB-1 · 3 turns · ↑ 410  ↓ 65  ⟲ 0  ✎ 0 · $0.00"
    )


def test_use_case_shows_the_agents_share_on_each_row_that_has_agent_turns() -> None:
    agent = TurnRole.AGENT
    turns = FakePerTurnStore(
        [
            TurnUsage("JOB-1_001", 100, 20, None, "m", role=agent),  # a prior session's agent
            TurnUsage("JOB-1_002", 300, 40, None, "m"),  # the current session: main only
        ]
    )
    out = _use_case(FakeUsageStore(), _NO_WORKSPACE, turns).execute("{}", "JOB-1", "JOB-1_002")
    # the session had no agent turns: today's line; the job did: shares
    assert out == (
        "  session JOB-1_002 · 1 turns · ↑ 300  ↓ 40  ⟲ 0  ✎ 0 · $0.00\n"
        "  job JOB-1 · 2 turns (50%) · ↑ 400 (25%)  ↓ 60 (33%)  ⟲ 0  ✎ 0 · $0.00"
    )


def test_use_case_shows_the_share_of_the_main_turns_the_agents_caused() -> None:
    turns = FakePerTurnStore(
        [
            TurnUsage("JOB-1_001", 300, 40, None, "m"),  # the user's prompt
            TurnUsage("JOB-1_001", 100, 20, None, "m", caused_by_agent=True),  # a report
        ]
    )
    out = _use_case(FakeUsageStore(), _NO_WORKSPACE, turns).execute("{}", "JOB-1", "JOB-1_001")
    assert (
        out == "  session JOB-1_001 · 2 turns (+50%) · ↑ 400 (+25%)  ↓ 60 (+33%)  ⟲ 0  ✎ 0 · $0.00"
    )


def test_use_case_has_no_footer_without_job_usage() -> None:
    out = _use_case(FakeUsageStore(), _NO_WORKSPACE).execute(
        json.dumps(_CLAUDE_PAYLOAD), "JOB-1", "JOB-1_001"
    )
    assert "\n" not in out  # no turns recorded and the fake reports no costs


def test_use_case_skips_recording_without_job_or_session() -> None:
    usage = FakeUsageStore()
    _use_case(usage, _NO_WORKSPACE).execute(json.dumps(_CLAUDE_PAYLOAD), None, None)
    assert usage.recorded == []


def test_use_case_tolerates_bad_json() -> None:
    usage = FakeUsageStore()
    line = _use_case(usage, _NO_WORKSPACE).execute("not json", "J", "J_1")
    assert line == ""
    assert usage.recorded == []


# ── elapsed time on the footer rows ──
@pytest.mark.parametrize(
    ("seconds", "rendered"),
    [
        (0, "0s"),
        (45, "45s"),
        (12 * 60, "12m"),
        (2 * 3600, "2h"),  # the second unit is dropped when it is zero
        (2 * 3600 + 45 * 60, "2h45m"),
        (3600 + 5 * 60, "1h05m"),  # zero-padded so the width does not jump
        (5 * 86400, "5d"),
        (86400 + 20 * 3600, "1d20h"),
        (-10, "0s"),  # a clock that went backwards is not a negative age
    ],
)
def test_format_age_uses_two_significant_units(seconds: int, rendered: str) -> None:
    assert format_age(seconds) == rendered


def test_the_age_is_bound_to_the_name_not_added_as_a_field() -> None:
    # Layout B: the dot separators read as a list of measurements -- turns, tokens,
    # dollars -- and the age is a property of the thing measured, not one more of them.
    row = render_usage_row("session", "JOB-1_002", 3, _TOKENS, 0.43, 6300)
    assert row.startswith("  session JOB-1_002 (1h45m) · ")


def test_a_row_without_an_age_is_unchanged() -> None:
    # A session launched but never prompted has no first turn, so it has no age.
    assert (
        render_usage_row("session", "JOB-1_002", 0, TokenCounts(), 0.0)
        == "  session JOB-1_002 · $0.00"
    )


_EPOCH = 1_700_000_000.0  # a real wall-clock, not the 0.0 that means "not recorded"


def test_the_footer_shows_how_long_the_session_and_job_have_been_going() -> None:
    # The session's age runs from its own first turn; the job's from the first turn of
    # any of its sessions -- so a job outlives the session you happen to be in.
    hour = 3600.0
    turns = FakePerTurnStore(
        [
            TurnUsage("JOB-1_001", 10, 5, None, "m", timestamp=_EPOCH),  # an earlier session
            TurnUsage("JOB-1_002", 10, 5, None, "m", timestamp=_EPOCH + 20 * hour),
        ]
    )
    line = _use_case(FakeUsageStore(), _NO_WORKSPACE, turns, now=_EPOCH + 24 * hour).execute(
        "{}", "JOB-1", "JOB-1_002"
    )
    assert "session JOB-1_002 (4h)" in line
    assert "job JOB-1 (1d)" in line


def test_a_session_with_no_turns_yet_shows_no_age() -> None:
    turns = FakePerTurnStore([TurnUsage("JOB-1_001", 10, 5, None, "m", timestamp=_EPOCH)])
    line = _use_case(FakeUsageStore(), _NO_WORKSPACE, turns, now=_EPOCH + 3600.0).execute(
        "{}", "JOB-1", "JOB-1_002"
    )
    assert "session JOB-1_002 · " in line  # named, but no parenthesised age
    assert "session JOB-1_002 (" not in line


def test_a_turn_with_no_recorded_time_does_not_anchor_the_age() -> None:
    # TurnUsage.timestamp defaults to 0.0 meaning "not recorded". Letting that count
    # would date every job to 1970 the moment one unstamped turn slipped in.
    turns = FakePerTurnStore(
        [
            TurnUsage("JOB-1_002", 10, 5, None, "m"),  # unstamped
            TurnUsage("JOB-1_002", 10, 5, None, "m", timestamp=_EPOCH),
        ]
    )
    line = _use_case(FakeUsageStore(), _NO_WORKSPACE, turns, now=_EPOCH + 7200.0).execute(
        "{}", "JOB-1", "JOB-1_002"
    )
    assert "(2h)" in line


def test_token_counts_sum_each_kind_over_the_turns() -> None:
    turns = [
        TurnUsage("S", 10, 2, None, "m", cache_creation_tokens=100, cache_read_tokens=1_000),
        TurnUsage("S", 5, 3, None, "m", cache_creation_tokens=0, cache_read_tokens=1_200),
    ]
    assert TokenCounts.of(turns) == TokenCounts(15, 5, 2_200, 100)


# ── context colour ──
_YELLOW, _RED, _RESET = "\033[33m", "\033[31m", "\033[0m"


@pytest.mark.parametrize(
    ("tokens", "window", "level"),
    [
        (60_000, 200_000, ContextLevel.OK),
        (140_000, 200_000, ContextLevel.WARN),  # 70% of the window
        (180_000, 200_000, ContextLevel.ALERT),  # 90%
        (200_000, 1_000_000, ContextLevel.WARN),  # 20%, but 200k long
        (400_000, 1_000_000, ContextLevel.ALERT),  # 40%, but 400k long
    ],
)
def test_the_worse_of_the_fill_and_the_size_sets_the_level(
    tokens: int, window: int, level: ContextLevel
) -> None:
    status = _status(context_tokens=tokens, context_window_size=window)
    assert ContextThresholds().level(status) is level


def test_the_reported_percentage_counts_without_token_figures() -> None:
    assert ContextThresholds().level(_status(context_pct=92)) is ContextLevel.ALERT
    assert ContextThresholds().level(_status()) is ContextLevel.OK


def test_a_zero_size_threshold_turns_that_rule_off() -> None:
    status = _status(context_tokens=500_000, context_window_size=1_000_000)
    assert ContextThresholds(warn_tokens=0, alert_tokens=0).level(status) is ContextLevel.OK


def test_only_the_context_block_is_painted() -> None:
    status = _status(model="Opus", context_tokens=450_000, context_window_size=1_000_000)
    line = render_statusline(status, _NO_WORKSPACE, ContextThresholds())
    assert line == f"Opus  ·  {_RED}ctx 450k/1M (45%){_RESET}"
    calm = _status(model="Opus", context_tokens=150_000, context_window_size=1_000_000)
    assert render_statusline(calm, _NO_WORKSPACE, ContextThresholds()) == (
        "Opus  ·  ctx 150k/1M (15%)"
    )


def test_without_thresholds_nothing_is_painted() -> None:
    status = _status(context_tokens=450_000, context_window_size=1_000_000)
    assert render_statusline(status, _NO_WORKSPACE) == "ctx 450k/1M (45%)"


def test_a_warning_is_yellow() -> None:
    status = _status(context_pct=75)
    assert render_statusline(status, _NO_WORKSPACE, ContextThresholds()) == (
        f"{_YELLOW}ctx 75%{_RESET}"
    )


def test_no_color_turns_the_colour_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    assert composition._context_thresholds() is None
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setattr(composition.config, "statusline_color", lambda: True)
    monkeypatch.setattr(
        composition.config, "context_thresholds", lambda: (50, 80, 100_000, 300_000)
    )
    assert composition._context_thresholds() == ContextThresholds(50, 80, 100_000, 300_000)


# ── tool calls ──
def test_the_tools_show_their_total_and_the_three_most_called() -> None:
    tools = ToolCalls.from_counts({"Bash": 640, "WebSearch": 310, "Read": 180, "Edit": 9})
    row = render_usage_row("job", "JOB-1", 3, TokenCounts(1, 1), 0.5, tools=tools)
    assert row == (
        "  job JOB-1 · 3 turns · ↑ 1  ↓ 1  ⟲ 0  ✎ 0 · "
        "⚒ 1.1k (Bash 640, WebSearch 310, Read 180, …) · $0.50"
    )


def test_no_tool_calls_leave_the_row_unchanged() -> None:
    row = render_usage_row("job", "JOB-1", 3, TokenCounts(1, 1), 0.5, tools=ToolCalls())
    assert "⚒" not in row


def test_use_case_counts_the_tools_of_each_row() -> None:
    turns = FakePerTurnStore(
        [
            TurnUsage("JOB-1_001", 1, 1, None, "m", tool_calls=ToolCalls.of(["Bash"])),
            TurnUsage("JOB-1_002", 1, 1, None, "m", tool_calls=ToolCalls.of(["Bash", "Read"])),
        ]
    )
    out = _use_case(FakeUsageStore(), _NO_WORKSPACE, turns).execute("{}", "JOB-1", "JOB-1_002")
    session, job = out.splitlines()
    assert "⚒ 2 (Bash 1, Read 1)" in session
    assert "⚒ 3 (Bash 2, Read 1)" in job
