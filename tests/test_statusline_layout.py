# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the status line's configurable layout: the model, its config, its rendering."""

from pathlib import Path

from generic_ml_wrapper.adapter.outbound.config.tomlkit_config_writer import TomlkitConfigWriter
from generic_ml_wrapper.application.domain.model.agent_usage import AgentUsage
from generic_ml_wrapper.application.domain.model.client_status import ClientStatus
from generic_ml_wrapper.application.domain.model.statusline_layout import (
    AGENT_FIELDS,
    LINE_BLOCKS,
    ROW_FIELDS,
    StatuslineLayout,
)
from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts
from generic_ml_wrapper.application.domain.model.tool_calls import ToolCalls
from generic_ml_wrapper.application.domain.model.workspace import Workspace
from generic_ml_wrapper.application.domain.service.statusline_renderer import (
    render_statusline,
    render_usage_row,
)
from generic_ml_wrapper.application.usecase.statusline_layout_settings import (
    StatuslineLayoutSettingsUseCase,
)
from generic_ml_wrapper.common import config

_REPO = Workspace(folder="~/dev/app", repo="app", branch="main", short_sha="abc1234", dirty=0)
_STATUS = ClientStatus(
    model="Opus 4.8", context_pct=34, session_cost_usd=0.43, extras=("quota wk 47%",)
)
_TOKENS = TokenCounts(input=100, output=50, cache_read=1000, cache_write=10)
_AGENTS = AgentUsage(1, TokenCounts(input=50, output=25, cache_read=500, cache_write=5))
_TOOLS = ToolCalls.from_counts({"Bash": 3})


# ── the model ──
def test_the_default_layout_is_the_full_line() -> None:
    layout = StatuslineLayout.of()
    assert layout.line == LINE_BLOCKS
    assert layout.rows == ROW_FIELDS
    assert layout.agents == frozenset(AGENT_FIELDS)


def test_unknown_and_repeated_names_are_dropped_in_order() -> None:
    layout = StatuslineLayout.of(["git", "nonsense", "model", "git"], [], ["tools", "input"])
    assert layout.line == ("git", "model")
    assert layout.rows == ()
    assert layout.agents == frozenset({"input"})  # tools has no agents' share


# ── rendering ──
def test_the_live_line_follows_the_layout() -> None:
    layout = StatuslineLayout.of(line=["git", "cost", "model"])
    assert render_statusline(_STATUS, _REPO, layout=layout) == (
        "git app/main abc1234  ·  $0.43  ·  Opus 4.8"
    )


def test_a_row_shows_its_fields_in_order_with_agents_only_where_asked() -> None:
    layout = StatuslineLayout.of(
        rows=["turns", "cache_read", "input", "tools", "cost"], agents=["input"]
    )
    row = render_usage_row("job", "J", 2, _TOKENS, 0.5, agents=_AGENTS, tools=_TOOLS, layout=layout)
    assert row == "  job J · 2 turns · ⟲ 1k  ↑ 100 (50%) · ⚒ 3 (Bash 3) · $0.50"


def test_token_kinds_apart_in_the_order_are_separate_fields() -> None:
    layout = StatuslineLayout.of(rows=["input", "cost", "output"], agents=[])
    row = render_usage_row("job", "J", 2, _TOKENS, 0.5, layout=layout)
    assert row == "  job J · ↑ 100 · $0.50 · ↓ 50"


def test_an_unmetered_row_shows_only_what_needs_no_turns() -> None:
    layout = StatuslineLayout.of(rows=["turns", "input", "cost"])
    assert render_usage_row("job", "J", 0, TokenCounts(), 0.5, layout=layout) == "  job J · $0.50"


# ── config ──
def test_the_layout_reads_back_what_was_saved(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("[statusline]\ncolor = false  # keep me\n", encoding="utf-8")
    settings = StatuslineLayoutSettingsUseCase(TomlkitConfigWriter(), lambda: path)
    saved = StatuslineLayout(("model", "cost"), ("cost", "turns"), frozenset({"turns"}))
    settings.save(saved)
    assert settings.load() == saved
    text = path.read_text(encoding="utf-8")
    assert "color = false  # keep me" in text
    assert 'line = ["model", "cost"]' in text


def test_an_ill_typed_layout_key_takes_its_default(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[statusline]\nline = "model"\nrows = ["cost", 3]\n', encoding="utf-8")
    assert config.statusline_layout(path) == (None, None, None)
