# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the readable usage tables the TUI's Export view shows."""

from generic_ml_wrapper.adapter.inbound.cli.usage_view import usage_tables
from generic_ml_wrapper.application.domain.model.turn_origin import TurnRole
from generic_ml_wrapper.application.port.inbound.export_usage import (
    AgentTotal,
    ModelTotal,
    SessionTotal,
    ToolTotal,
    UsageReport,
)

_REPORT = UsageReport(
    "JOB-1",
    models=(ModelTotal("opus", 3, 1_500, 200_000, 50_000, 2_250_000, 4_000.0),),
    agents=(
        AgentTotal(TurnRole.MAIN, None, 2, 500, 100_000, 25_000, 1_874_400, 3_000.0),
        AgentTotal(TurnRole.AGENT, "scout", 1, 1_000, 100_000, 25_000, 375_600, 1_000.0),
    ),
    sessions=(
        SessionTotal("JOB-1_001", 3, 1_500, 200_000, 50_000, 2_250_000, 4_000.0, 1.5),
        SessionTotal("JOB-1_002", 0, 0, 0, 0, 0, 0.0, None),
    ),
    tools=(ToolTotal("Bash", 3), ToolTotal("Read", 1)),
    turn_count=3,
    input_tokens=1_500,
    output_tokens=200_000,
    cache_read_tokens=50_000,
    cache_write_tokens=2_250_000,
    duration_s=4_000.0,
    total_usd=1.5,
)


def test_the_summary_reads_in_k_m_and_hours_with_the_agents_share() -> None:
    summary, _ = usage_tables(_REPORT)
    assert summary == ("3 turns · 1h06m · ↑ 1.5k  ↓ 200k  ⟲ 50k  ✎ 2.2M · agents 20% · $1.50")


def test_each_grouping_is_a_table_in_tab_order() -> None:
    _, tables = usage_tables(_REPORT)
    assert [title for title, _, _ in tables] == ["Model", "Agent", "Tool", "Session"]


def test_a_token_table_compacts_its_counts_and_shares_the_whole() -> None:
    _, tables = usage_tables(_REPORT)
    _, columns, rows = tables[1]
    assert columns == (
        "Agent",
        "Calls",
        "Input",
        "Output",
        "Cache write",
        "Cache read",
        "%",
        "Duration",
    )
    assert rows[1] == ("scout", "1", "1k", "100k", "375.6k", "25k", "20%", "16m")


def test_the_session_table_ends_with_the_client_cost_or_a_dash() -> None:
    _, tables = usage_tables(_REPORT)
    _, columns, rows = tables[3]
    assert columns[-1] == "Cost"
    assert [row[-1] for row in rows] == ["$1.50", "-"]


def test_a_job_without_agents_or_tools_has_no_such_tabs() -> None:
    report = UsageReport("JOB-1", models=_REPORT.models, sessions=_REPORT.sessions[:1])
    summary, tables = usage_tables(report)
    assert [title for title, _, _ in tables] == ["Model", "Session"]
    assert "agents" not in summary
