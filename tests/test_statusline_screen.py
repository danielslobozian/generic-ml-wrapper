# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for Config > Status line in ``gmlw tui`` (Pilot-driven)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from textual.pilot import Pilot
from textual.widgets import Label, ListView, Static, TabbedContent

from generic_ml_wrapper.adapter.inbound.tui.menu_app import JobChoice, MenuApp, MenuChoice
from generic_ml_wrapper.adapter.inbound.tui.statusline_screen import (
    StatuslineScreen,
    StatuslineSettings,
)
from generic_ml_wrapper.application.domain.model.statusline_layout import StatuslineLayout

_JOBS = [JobChoice(job="alpha", session_count=1)]


class _Store:
    """An in-memory layout, recording every save."""

    def __init__(self, layout: StatuslineLayout | None = None) -> None:
        self.layout = layout or StatuslineLayout()
        self.saves: list[StatuslineLayout] = []

    def settings(self) -> StatuslineSettings:
        def save(layout: StatuslineLayout) -> None:
            self.layout = layout
            self.saves.append(layout)

        return StatuslineSettings(load=lambda: self.layout, save=save)


def _drive(store: _Store, script: Callable[[Pilot[MenuChoice | None]], Awaitable[None]]) -> None:
    async def scenario() -> None:
        app = MenuApp(_JOBS, statusline=store.settings())
        async with app.run_test(size=(100, 30)) as pilot:
            await script(pilot)

    asyncio.run(scenario())


def _rows(pilot: Pilot[MenuChoice | None], list_id: str) -> list[str]:
    view = pilot.app.screen.query_one(f"#{list_id}", ListView)
    return [str(label.render()) for label in view.query(Label)]


def test_config_menu_opens_the_status_line_screen() -> None:
    async def script(pilot: Pilot[MenuChoice | None]) -> None:
        await pilot.press("down", "down", "enter")  # top → Config
        await pilot.press(*["down"] * 7, "enter")  # Config → Status line (8th row)
        assert isinstance(pilot.app.screen, StatuslineScreen)

    _drive(_Store(), script)


def test_space_hides_a_block_and_saves_at_once() -> None:
    store = _Store()

    async def script(pilot: Pilot[MenuChoice | None]) -> None:
        pilot.app.push_screen(StatuslineScreen(store.settings()))
        await pilot.pause()
        await pilot.press("space")  # hide model
        assert _rows(pilot, "sl_line")[0].startswith("☐ Model")

    _drive(store, script)
    assert store.layout.line == ("context", "quota", "cost", "git", "folder")


def test_shift_down_moves_a_block_and_the_cursor_follows() -> None:
    store = _Store()

    async def script(pilot: Pilot[MenuChoice | None]) -> None:
        pilot.app.push_screen(StatuslineScreen(store.settings()))
        await pilot.pause()
        await pilot.press("shift+down", "shift+down")
        assert pilot.app.screen.query_one("#sl_line", ListView).index == 2

    _drive(store, script)
    assert store.layout.line == ("context", "quota", "model", "cost", "git", "folder")


def test_the_rows_tab_toggles_the_agents_share_per_field() -> None:
    store = _Store()

    async def script(pilot: Pilot[MenuChoice | None]) -> None:
        pilot.app.push_screen(StatuslineScreen(store.settings()))
        await pilot.pause()
        await pilot.press("right")
        tabs = pilot.app.screen.query_one("#sl_tabs", TabbedContent)
        assert tabs.active == "sl_rows_tab"
        await pilot.press("down", "a")  # turns: agents off
        assert "agents ☐" in _rows(pilot, "sl_rows")[1]
        await pilot.press("up", "a")  # cost has no share: refused
        detail = pilot.app.screen.query_one("#detail", Static)
        assert "no agents' share" in str(detail.render())

    _drive(store, script)
    assert "turns" not in store.layout.agents
    assert len(store.saves) == 1


def test_a_hidden_block_is_listed_after_the_shown_ones() -> None:
    store = _Store(StatuslineLayout.of(line=["git", "model"]))

    async def script(pilot: Pilot[MenuChoice | None]) -> None:
        pilot.app.push_screen(StatuslineScreen(store.settings()))
        await pilot.pause()
        rows = _rows(pilot, "sl_line")
        assert rows[0] == "☑ Git"
        assert rows[1] == "☑ Model"
        assert rows[2] == "☐ Context"

    _drive(store, script)
