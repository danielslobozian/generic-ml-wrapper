# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the cursor status parser and client-based parser selection."""

from pathlib import Path

from generic_ml_wrapper.adapter.outbound.status.catalogued_status_parsers import (
    CataloguedStatusParsersAdapter,
)
from generic_ml_wrapper.adapter.outbound.status.claude_status_parser import (
    ClaudeStatusParserAdapter,
)
from generic_ml_wrapper.adapter.outbound.status.cursor_status_parser import (
    CursorStatusParserAdapter,
)


def _parser(tmp_path: Path) -> CursorStatusParserAdapter:
    """A parser whose plan cache is absent, which is the ordinary case."""
    return CursorStatusParserAdapter(tmp_path / "cursor-plan.json")


def test_parses_model_and_context_like_claude(tmp_path: Path) -> None:
    status = _parser(tmp_path).parse(
        {"model": {"display_name": "Claude Sonnet 4.5"}, "context_window": {"used_percentage": 41}}
    )
    assert status.model == "Claude Sonnet 4.5"
    assert status.context_pct == 41


def test_cursor_has_no_session_cost(tmp_path: Path) -> None:
    # cursor is subscription-metered: no per-session cost on the wire.
    status = _parser(tmp_path).parse({"cost": {"total_cost_usd": 9.9}})
    assert status.session_cost_usd is None


def test_plan_block_rendered_when_present(tmp_path: Path) -> None:
    status = _parser(tmp_path).parse({"plan": {"auto_pct": 45, "api_pct": 12}})
    assert status.extras == ("plan auto 45% · api 12%",)


def test_plan_block_omitted_when_absent(tmp_path: Path) -> None:
    # Cursor exposes plan pools via its dashboard API, not the status payload — so
    # with no plan table, the allowance block is simply omitted (not faked).
    assert _parser(tmp_path).parse({"model": {"display_name": "x"}}).extras == ()


def test_empty_payload_is_all_none(tmp_path: Path) -> None:
    status = _parser(tmp_path).parse({})
    assert status.model is None
    assert status.context_pct is None
    assert status.session_cost_usd is None
    assert status.extras == ()


def test_cursor_gets_its_own_parser(tmp_path: Path) -> None:
    parsers = CataloguedStatusParsersAdapter(tmp_path / "cursor-plan.json")
    assert isinstance(parsers.for_client("cursor"), CursorStatusParserAdapter)


def test_every_other_client_gets_claudes_parser(tmp_path: Path) -> None:
    """Both host clients pipe a Claude-compatible payload, so it is the safe default.

    A status line whose one duty is to always print something must not fail over a client
    name it did not recognise.
    """
    parsers = CataloguedStatusParsersAdapter(tmp_path / "cursor-plan.json")
    for client in ("claude", None, "codex"):
        assert isinstance(parsers.for_client(client), ClaudeStatusParserAdapter)


# ── the cached allowance, which cursor does not pipe to the status line ──
def test_the_cached_plan_is_folded_in_when_the_payload_has_none(tmp_path: Path) -> None:
    cache = tmp_path / "cursor-plan.json"
    cache.write_text('{"auto_pct": 6.2, "api_pct": 3.4}', encoding="utf-8")

    status = CursorStatusParserAdapter(cache).parse({"model": {"display_name": "Composer"}})

    assert status.extras == ("plan auto 6% · api 3%",)


def test_a_payload_that_carries_its_own_plan_wins(tmp_path: Path) -> None:
    """It came from cursor this turn; the cache is whatever a fetcher last wrote."""
    cache = tmp_path / "cursor-plan.json"
    cache.write_text('{"auto_pct": 1, "api_pct": 1}', encoding="utf-8")

    status = CursorStatusParserAdapter(cache).parse({"plan": {"auto_pct": 9, "api_pct": 8}})

    assert status.extras == ("plan auto 9% · api 8%",)


def test_an_unreadable_cache_is_simply_no_plan(tmp_path: Path) -> None:
    cache = tmp_path / "cursor-plan.json"
    cache.write_text("not json", encoding="utf-8")

    assert CursorStatusParserAdapter(cache).parse({"model": {"display_name": "x"}}).extras == ()
