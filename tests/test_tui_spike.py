# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SPIKE: prove the object-first menu is drivable and hands back a resume choice.

The repo has no pytest-asyncio, so each scenario is wrapped in ``asyncio.run`` -- Textual's
``run_test``/``Pilot`` is the only async surface and needs nothing more than an event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from textual.pilot import Pilot
from textual.widgets import ListView

from generic_ml_wrapper.adapter.inbound.tui.spike_app import (
    JobChoice,
    MenuChoice,
    SpikeMenuApp,
    SwitchChoice,
    Switcher,
)

_JOBS = [JobChoice(job="alpha", session_count=3), JobChoice(job="beta", session_count=1)]


def _persona_switcher(
    current: str = "mentor", apply: Callable[[str], str] | None = None
) -> dict[str, Switcher]:
    """A fresh persona switcher (mentor/coach) for one test -- never share the mutable state."""
    return {
        "persona": Switcher(
            crumb="gmlw > Config > Persona",
            choices=[
                SwitchChoice("mentor", "mentor", "steady and instructive"),
                SwitchChoice("coach", "coach", "brisk and demanding"),
            ],
            current=current,
            apply=apply or (lambda value: f"persona set to '{value}'"),
        )
    }


def _drive(script: Callable[[Pilot], Awaitable[None]]) -> MenuChoice | None:
    """Run the spike app under Pilot, apply ``script``, return the app's exit value."""

    async def scenario() -> MenuChoice | None:
        app = SpikeMenuApp(_JOBS)
        async with app.run_test(size=(90, 30)) as pilot:
            await script(pilot)
        return app.return_value

    return asyncio.run(scenario())


def test_resume_flow_returns_chosen_job() -> None:
    """Top → Job → Resume → pick the first job → resume alpha."""

    async def script(pilot: Pilot) -> None:
        await pilot.press("enter")  # Job (first top-menu row) → Job menu
        await pilot.press("down")  # New → Resume
        await pilot.press("enter")  # Resume → job picker
        await pilot.press("enter")  # pick the first job (alpha)

    assert _drive(script) == MenuChoice(action="resume", job="alpha")


def test_quit_from_top_returns_none() -> None:
    """The 'q' binding at the front door exits with no choice."""

    async def script(pilot: Pilot) -> None:
        await pilot.press("q")

    assert _drive(script) is None


def test_escape_walks_back_up_the_tree() -> None:
    """Into Job, into Resume, then Esc twice climbs back to the top, then quit."""

    async def script(pilot: Pilot) -> None:
        await pilot.press("enter")  # → Job menu
        await pilot.press("down", "enter")  # → job picker (Resume)
        await pilot.press("escape")  # back to Job menu
        await pilot.press("escape")  # back to top
        await pilot.press("q")  # quit from the top

    assert _drive(script) is None


def test_escape_at_top_exits() -> None:
    """At the front door there is nothing to pop to, so Back leaves gmlw."""

    async def script(pilot: Pilot) -> None:
        await pilot.press("escape")

    assert _drive(script) is None


def test_switcher_persists_via_the_injected_apply() -> None:
    """Top → Config → Persona → pick 'coach' → the switcher's apply is called with 'coach'."""
    calls: list[str] = []
    switchers = _persona_switcher(apply=lambda value: (calls.append(value), f"set {value}")[1])

    async def scenario() -> None:
        app = SpikeMenuApp(_JOBS, switchers=switchers)
        async with app.run_test(size=(90, 30)) as pilot:
            await pilot.press("down", "down", "enter")  # top → Config (3rd row)
            await pilot.press("down", "down", "down", "enter")  # Config → Persona (4th row)
            await pilot.press("down", "enter")  # personas: mentor → coach → pick

    asyncio.run(scenario())
    assert calls == ["coach"]
    assert switchers["persona"].current == "coach"  # current advanced to the picked value


def test_switcher_keeps_the_cursor_in_place() -> None:
    """Selecting an option updates the dots in place -- the highlight must not reset."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = SpikeMenuApp(_JOBS, switchers=_persona_switcher(current="mentor"))
        async with app.run_test(size=(90, 30)) as pilot:
            await pilot.press("down", "down", "enter")  # → Config
            await pilot.press("down", "down", "down", "enter")  # → Persona picker
            await pilot.press("down", "enter")  # highlight + pick 'coach' (index 1)
            await pilot.pause()
            seen["index"] = app.screen.query_one("#menu", ListView).index

    asyncio.run(scenario())
    assert seen["index"] == 1  # cursor stayed on the row that was picked, not reset to top


def test_switcher_menu_opens_on_the_active_option() -> None:
    """The picker starts with the cursor on the current value, not the first row."""
    index: dict[str, object] = {}

    async def scenario() -> None:
        # current 'coach' is the second of the two options (index 1).
        app = SpikeMenuApp(_JOBS, switchers=_persona_switcher(current="coach"))
        async with app.run_test(size=(90, 30)) as pilot:
            await pilot.press("down", "down", "enter")  # → Config
            await pilot.press("down", "down", "down", "enter")  # → Persona picker
            await pilot.pause()
            index["value"] = app.screen.query_one("#menu", ListView).index

    asyncio.run(scenario())
    assert index["value"] == 1
