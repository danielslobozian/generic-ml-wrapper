# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the cursor status parser and client-based parser selection."""

from generic_ml_wrapper.adapter.outbound.status.claude_status_parser import ClaudeStatusParser
from generic_ml_wrapper.adapter.outbound.status.cursor_status_parser import CursorStatusParser
from generic_ml_wrapper.application.usecase.render_statusline import RenderStatuslineUseCase
from generic_ml_wrapper.application.wiring.composition import build_render_statusline


def test_parses_model_and_context_like_claude() -> None:
    status = CursorStatusParser().parse(
        {"model": {"display_name": "Claude Sonnet 4.5"}, "context_window": {"used_percentage": 41}}
    )
    assert status.model == "Claude Sonnet 4.5"
    assert status.context_pct == 41


def test_cursor_has_no_session_cost() -> None:
    # cursor is subscription-metered: no per-session cost on the wire.
    status = CursorStatusParser().parse({"cost": {"total_cost_usd": 9.9}})
    assert status.session_cost_usd is None


def test_plan_block_rendered_when_present() -> None:
    status = CursorStatusParser().parse({"plan": {"auto_pct": 45, "api_pct": 12}})
    assert status.extras == ("plan auto 45% · api 12%",)


def test_plan_block_omitted_when_absent() -> None:
    # Cursor exposes plan pools via its dashboard API, not the status payload — so
    # with no plan table, the allowance block is simply omitted (not faked).
    assert CursorStatusParser().parse({"model": {"display_name": "x"}}).extras == ()


def test_empty_payload_is_all_none() -> None:
    status = CursorStatusParser().parse({})
    assert status.model is None
    assert status.context_pct is None
    assert status.session_cost_usd is None
    assert status.extras == ()


def test_build_selects_cursor_parser_for_cursor() -> None:
    use_case = build_render_statusline("cursor")
    assert isinstance(use_case, RenderStatuslineUseCase)
    assert isinstance(use_case._parser, CursorStatusParser)


def test_build_falls_back_to_claude_parser() -> None:
    for client in ("claude", None, "codex"):
        use_case = build_render_statusline(client)
        assert isinstance(use_case, RenderStatuslineUseCase)
        assert isinstance(use_case._parser, ClaudeStatusParser)
