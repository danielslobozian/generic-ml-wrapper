# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for status parsing, rendering, and the RenderStatuslineUseCase use case."""

import json

import pytest

from generic_ml_wrapper.adapter.outbound.diagnostics.null_diagnostics import NullDiagnosticsAdapter
from generic_ml_wrapper.adapter.outbound.i18n.json_catalog_localizer import (
    JsonCatalogLocalizerFactory,
)
from generic_ml_wrapper.adapter.outbound.status.claude_status_parser import (
    ClaudeStatusParserAdapter,
)
from generic_ml_wrapper.application.domain.model.client_status import ClientStatus
from generic_ml_wrapper.application.domain.model.run_handoff import RunHandoff
from generic_ml_wrapper.application.domain.model.session_cost import SessionCost
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.domain.model.workspace import Workspace
from generic_ml_wrapper.application.domain.service.statusline_renderer import StatuslineRenderer
from generic_ml_wrapper.application.port.outbound.client_status import ClientStatusParserPort
from generic_ml_wrapper.application.port.outbound.localizer import LocalizerPort
from generic_ml_wrapper.application.port.outbound.per_turn_metering import PerTurnMeteringPort
from generic_ml_wrapper.application.port.outbound.run_handoff import RunHandoffPort
from generic_ml_wrapper.application.port.outbound.status_parsers import StatusParsersPort
from generic_ml_wrapper.application.port.outbound.usage_store import UsageStorePort
from generic_ml_wrapper.application.port.outbound.workspace import WorkspaceInspectorPort
from generic_ml_wrapper.application.usecase.render_statusline import RenderStatuslineService

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


def _localizer() -> LocalizerPort:
    """The real English catalogue: these tests assert behaviour, not translations."""
    return JsonCatalogLocalizerFactory().load("en")


class FakeUsageStore(UsageStorePort):
    def __init__(self, *, refuse: bool = False) -> None:
        self.recorded: list[tuple[str, str, float]] = []
        self.refuse = refuse

    def record_session_cost(self, job: str, cost: SessionCost) -> None:
        if self.refuse:
            message = "no such session"
            raise RuntimeError(message)
        self.recorded.append((job, cost.session_id, cost.cost_usd))

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
    status = ClaudeStatusParserAdapter(clock=_clock).parse(_CLAUDE_PAYLOAD)
    assert status.model == "Opus 4.8"
    assert status.context_pct == 34
    assert status.context_window_size == 200000
    assert status.context_tokens == 68000
    assert status.session_cost_usd == 0.4321
    assert status.extras == ("quota 5h 12% (↻ 12m) · wk 47% (↻ 3d)",)


def test_claude_parser_reads_partial_quota() -> None:
    # No resets_at → the window renders as percentage only (reset marker omitted).
    status = ClaudeStatusParserAdapter().parse(
        {"rate_limits": {"five_hour": {"used_percentage": 80}}}
    )
    assert status.extras == ("quota 5h 80%",)


def test_claude_parser_reset_durations() -> None:
    parser = ClaudeStatusParserAdapter(clock=_clock)

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
    parsed = ClaudeStatusParserAdapter().parse({})
    assert parsed == _status()
    assert parsed.extras == ()


# ── renderer ──
def test_render_omits_missing_fields() -> None:
    assert StatuslineRenderer().render_statusline(_status(), _NO_WORKSPACE) == ""
    assert (
        StatuslineRenderer().render_statusline(_status(model="Opus 4.8"), _NO_WORKSPACE)
        == "Opus 4.8"
    )


def test_render_context_shows_denominator() -> None:
    status = _status(context_pct=34, context_tokens=68000, context_window_size=200000)
    assert StatuslineRenderer().render_statusline(status, _NO_WORKSPACE) == "ctx 68k/200k (34%)"


def test_render_context_compact_and_computes_pct_when_absent() -> None:
    # 1M window, fractional-k tokens; percentage computed since the client omitted it.
    status = _status(context_tokens=155615, context_window_size=1_000_000)
    assert StatuslineRenderer().render_statusline(status, _NO_WORKSPACE) == "ctx 155.6k/1M (16%)"


def test_render_context_falls_back_to_pct_without_tokens_or_size() -> None:
    assert (
        StatuslineRenderer().render_statusline(_status(context_pct=34), _NO_WORKSPACE) == "ctx 34%"
    )


def test_render_full_line() -> None:
    status = _status(
        model="Opus 4.8", context_pct=34, extras=("quota 5h 12% · wk 47%",), session_cost_usd=0.43
    )
    line = StatuslineRenderer().render_statusline(status, _REPO)
    assert "git app/main abc1234 dirty:3" in line
    assert "📁 ~/dev/app" in line
    assert "Opus 4.8" in line
    assert "ctx 34%" in line
    assert "quota 5h 12% · wk 47%" in line
    assert "$0.43" in line


def test_render_places_extras_between_context_and_cost() -> None:
    status = _status(context_pct=34, extras=("quota 5h 12%", "plan auto 8%"), session_cost_usd=0.43)
    line = StatuslineRenderer().render_statusline(status, _NO_WORKSPACE)
    assert line == "ctx 34%  ·  quota 5h 12%  ·  plan auto 8%  ·  $0.43"


def test_render_git_omits_sha_and_dirty_when_clean() -> None:
    clean = Workspace(folder=None, repo="app", branch="main", short_sha=None, dirty=0)
    assert StatuslineRenderer().render_statusline(_status(), clean) == "git app/main"


def test_render_git_without_repo_name() -> None:
    detached = Workspace(folder=None, repo=None, branch="wip", short_sha=None, dirty=0)
    assert StatuslineRenderer().render_statusline(_status(), detached) == "git wip"


# ── usage footer rows ──
def test_render_usage_row_with_turns() -> None:
    assert (
        StatuslineRenderer().render_usage_row("job", "JOB-1", 3, 45194, 0.43)
        == "  job JOB-1 · 3 turns · 45.2k tok · $0.43"
    )


def test_render_usage_row_compacts_large_totals_to_k_m_g() -> None:
    # A heavy job's cache-dominated total stays scannable: k -> M -> G.
    assert "45.2k tok" in StatuslineRenderer().render_usage_row("job", "J", 3, 45_194, 1.0)
    assert "487M tok" in StatuslineRenderer().render_usage_row("job", "J", 900, 487_000_000, 1.0)
    assert "8.5G tok" in StatuslineRenderer().render_usage_row(
        "job", "wrapper", 3251, 8_472_936_150, 663.70
    )
    assert "999 tok" in StatuslineRenderer().render_usage_row(
        "job", "J", 1, 999, 1.0
    )  # below 1000 stays exact


def test_render_usage_row_without_turns_shows_only_cost() -> None:
    assert (
        StatuslineRenderer().render_usage_row("job", "JOB-1", 0, 0, 0.43) == "  job JOB-1 · $0.43"
    )


def test_render_usage_row_session_label() -> None:
    assert (
        StatuslineRenderer().render_usage_row("session", "JOB-1_002", 2, 100, 0.10)
        == "  session JOB-1_002 · 2 turns · 100 tok · $0.10"
    )


# ── use case ──
class _FixedParsers(StatusParsersPort):
    """One parser whatever the client: which parser is chosen is asserted elsewhere."""

    def for_client(self, client: str | None) -> ClientStatusParserPort:
        return ClaudeStatusParserAdapter(clock=_clock)


class _FakeHandoff(RunHandoffPort):
    """The run a launch would have announced to the status line."""

    def __init__(self, job: str | None = None, session: str | None = None) -> None:
        self._handoff = RunHandoff(job=job, session_id=session, client="claude")

    def current(self) -> RunHandoff:
        return self._handoff


def _use_case(  # noqa: PLR0913, PLR0917  (its ports, plus the run and the clock a test pins)
    usage: FakeUsageStore,
    workspace: Workspace,
    turns: FakePerTurnStore | None = None,
    now: float = 0.0,
    job: str | None = None,
    session: str | None = None,
) -> RenderStatuslineService:
    return RenderStatuslineService(
        _FixedParsers(),
        _FakeHandoff(job, session),
        usage,
        FakeWorkspaceInspector(workspace),
        turns or FakePerTurnStore(),
        NullDiagnosticsAdapter(),
        _localizer(),
        clock=lambda: now,
    )


def test_use_case_records_cost_and_renders() -> None:
    usage = FakeUsageStore()
    line = _use_case(usage, _REPO, job="JOB-1", session="JOB-1_001").execute(
        json.dumps(_CLAUDE_PAYLOAD)
    )
    assert "$0.43" in line
    assert "git app/main" in line
    assert usage.recorded == [("JOB-1", "JOB-1_001", 0.4321)]


def test_the_line_still_renders_when_the_store_refuses_the_cost() -> None:
    """A refused bookkeeping write must not blank the user's status bar.

    Reachable once the tables reference each other: a client whose wrapper process died
    outlives the session row it was launched under, and keeps piping status payloads at
    a session that is no longer there.
    """
    usage = FakeUsageStore(refuse=True)

    line = _use_case(usage, _REPO, job="JOB-1", session="JOB-1_001").execute(
        json.dumps(_CLAUDE_PAYLOAD)
    )

    assert "$0.43" in line
    assert "git app/main" in line
    assert usage.recorded == []


def test_use_case_shows_only_the_session_row_for_a_single_session() -> None:
    turns = FakePerTurnStore(
        [
            TurnUsage(
                "JOB-1_001", 3106, 7, None, "m", cache_creation_tokens=42081, cache_read_tokens=0
            )
        ]
    )
    out = _use_case(
        FakeUsageStore(), _NO_WORKSPACE, turns, job="JOB-1", session="JOB-1_001"
    ).execute("{}")
    # one session → just the current-session row (no separate job total)
    assert out == "  session JOB-1_001 · 1 turns · 45.2k tok · $0.00"


def test_use_case_shows_session_then_job_row_across_sessions() -> None:
    turns = FakePerTurnStore(
        [
            TurnUsage("JOB-1_001", 100, 20, None, "m"),  # a prior session
            TurnUsage("JOB-1_002", 300, 40, None, "m"),  # the current session
            TurnUsage("JOB-1_002", 10, 5, None, "m"),
        ]
    )
    out = _use_case(
        FakeUsageStore(), _NO_WORKSPACE, turns, job="JOB-1", session="JOB-1_002"
    ).execute("{}")
    # current session first, then the job total across both sessions
    assert out == (
        "  session JOB-1_002 · 2 turns · 355 tok · $0.00\n  job JOB-1 · 3 turns · 475 tok · $0.00"
    )


def test_use_case_has_no_footer_without_job_usage() -> None:
    out = _use_case(FakeUsageStore(), _NO_WORKSPACE, job="JOB-1", session="JOB-1_001").execute(
        json.dumps(_CLAUDE_PAYLOAD)
    )
    assert "\n" not in out  # no turns recorded and the fake reports no costs


def test_use_case_skips_recording_without_job_or_session() -> None:
    usage = FakeUsageStore()
    _use_case(usage, _NO_WORKSPACE, job=None, session=None).execute(json.dumps(_CLAUDE_PAYLOAD))
    assert usage.recorded == []


def test_use_case_tolerates_bad_json() -> None:
    usage = FakeUsageStore()
    line = _use_case(usage, _NO_WORKSPACE, job="J", session="J_1").execute("not json")
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
    assert StatuslineRenderer().format_age(seconds) == rendered


def test_the_age_is_bound_to_the_name_not_added_as_a_field() -> None:
    # Layout B: the dot separators read as a list of measurements -- turns, tokens,
    # dollars -- and the age is a property of the thing measured, not one more of them.
    row = StatuslineRenderer().render_usage_row("session", "JOB-1_002", 3, 45194, 0.43, 6300)
    assert row.startswith("  session JOB-1_002 (1h45m) · ")


def test_a_row_without_an_age_is_unchanged() -> None:
    # A session launched but never prompted has no first turn, so it has no age.
    assert (
        StatuslineRenderer().render_usage_row("session", "JOB-1_002", 0, 0, 0.0)
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
    line = _use_case(
        FakeUsageStore(),
        _NO_WORKSPACE,
        turns,
        now=_EPOCH + 24 * hour,
        job="JOB-1",
        session="JOB-1_002",
    ).execute("{}")
    assert "session JOB-1_002 (4h)" in line
    assert "job JOB-1 (1d)" in line


def test_a_session_with_no_turns_yet_shows_no_age() -> None:
    turns = FakePerTurnStore([TurnUsage("JOB-1_001", 10, 5, None, "m", timestamp=_EPOCH)])
    line = _use_case(
        FakeUsageStore(),
        _NO_WORKSPACE,
        turns,
        now=_EPOCH + 3600.0,
        job="JOB-1",
        session="JOB-1_002",
    ).execute("{}")
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
    line = _use_case(
        FakeUsageStore(),
        _NO_WORKSPACE,
        turns,
        now=_EPOCH + 7200.0,
        job="JOB-1",
        session="JOB-1_002",
    ).execute("{}")
    assert "(2h)" in line
