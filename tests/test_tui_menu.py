# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the object-first ``gmlw tui`` menu (Pilot-driven).

The repo has no pytest-asyncio, so each scenario is wrapped in ``asyncio.run`` -- Textual's
``run_test``/``Pilot`` is the only async surface and needs nothing more than an event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from textual.pilot import Pilot
from textual.widgets import Input, ListItem, ListView, Static

from generic_ml_wrapper.adapter.inbound.tui.menu_app import (
    CreateOutcome,
    JobChoice,
    MenuApp,
    MenuChoice,
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


def _drive(script: Callable[[Pilot[MenuChoice | None]], Awaitable[None]]) -> MenuChoice | None:
    """Run the menu app under Pilot, apply ``script``, return the app's exit value."""

    async def scenario() -> MenuChoice | None:
        app = MenuApp(_JOBS)
        async with app.run_test(size=(90, 30)) as pilot:
            await script(pilot)
        return app.return_value

    return asyncio.run(scenario())


def test_resume_flow_returns_chosen_job() -> None:
    """Top → Job → Resume → pick the first job → resume alpha."""

    async def script(pilot: Pilot[MenuChoice | None]) -> None:
        await pilot.press("enter")  # Job (first top-menu row) → Job menu
        await pilot.press("down")  # New → Resume
        await pilot.press("enter")  # Resume → job picker
        await pilot.press("enter")  # pick the first job (alpha)

    assert _drive(script) == MenuChoice(action="resume", job="alpha")


def test_quit_from_top_returns_none() -> None:
    """The 'q' binding at the front door exits with no choice."""

    async def script(pilot: Pilot[MenuChoice | None]) -> None:
        await pilot.press("q")

    assert _drive(script) is None


def test_escape_walks_back_up_the_tree() -> None:
    """Into Job, into Resume, then Esc twice climbs back to the top, then quit."""

    async def script(pilot: Pilot[MenuChoice | None]) -> None:
        await pilot.press("enter")  # → Job menu
        await pilot.press("down", "enter")  # → job picker (Resume)
        await pilot.press("escape")  # back to Job menu
        await pilot.press("escape")  # back to top
        await pilot.press("q")  # quit from the top

    assert _drive(script) is None


def test_escape_at_top_exits() -> None:
    """At the front door there is nothing to pop to, so Back leaves gmlw."""

    async def script(pilot: Pilot[MenuChoice | None]) -> None:
        await pilot.press("escape")

    assert _drive(script) is None


def test_switcher_persists_via_the_injected_apply() -> None:
    """Top → Config → Persona → pick 'coach' → the switcher's apply is called with 'coach'."""
    calls: list[str] = []
    switchers = _persona_switcher(apply=lambda value: (calls.append(value), f"set {value}")[1])

    async def scenario() -> None:
        app = MenuApp(_JOBS, switchers=switchers)
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
        app = MenuApp(_JOBS, switchers=_persona_switcher(current="mentor"))
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
        app = MenuApp(_JOBS, switchers=_persona_switcher(current="coach"))
        async with app.run_test(size=(90, 30)) as pilot:
            await pilot.press("down", "down", "enter")  # → Config
            await pilot.press("down", "down", "down", "enter")  # → Persona picker
            await pilot.pause()
            index["value"] = app.screen.query_one("#menu", ListView).index

    asyncio.run(scenario())
    assert index["value"] == 1


def _env_switcher(
    create: Callable[[str], CreateOutcome], current: str = "work"
) -> dict[str, Switcher]:
    """An environment switcher (one option + a create callback) for the create tests."""
    return {
        "environment": Switcher(
            crumb="gmlw > Config > Environment",
            choices=[SwitchChoice("work", "work", "the day job")],
            current=current,
            apply=lambda value: f"set {value}",
            create=create,
        )
    }


async def _open_env_switcher(pilot: Pilot[MenuChoice | None]) -> None:
    """Top → Config → Environment (Config row index 4)."""
    await pilot.press("down", "down", "enter")  # → Config
    await pilot.press("down", "down", "down", "down", "enter")  # → Environment switcher
    await pilot.pause()


def test_create_new_environment_adds_and_selects_it() -> None:
    """New → type a name → the create callback runs and the new option becomes current."""
    calls: list[str] = []

    def create(label: str) -> CreateOutcome:
        calls.append(label)
        return CreateOutcome(SwitchChoice(label.lower().replace(" ", "-"), label, ""), "ok")

    switchers = _env_switcher(create)

    async def scenario() -> None:
        app = MenuApp(_JOBS, switchers=switchers)
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_env_switcher(pilot)
            await pilot.press("down", "enter")  # onto the New row, open the form
            await pilot.pause()
            app.screen.query_one("#name", Input).value = "Client Project"
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()

    asyncio.run(scenario())
    assert calls == ["Client Project"]
    assert switchers["environment"].current == "client-project"
    assert [c.value for c in switchers["environment"].choices] == ["work", "client-project"]


def test_create_cancel_leaves_the_switcher_unchanged() -> None:
    """Esc in the create form creates nothing and the options are untouched."""
    calls: list[str] = []

    def create(label: str) -> CreateOutcome:
        calls.append(label)
        return CreateOutcome(SwitchChoice(label, label, ""), "ok")

    switchers = _env_switcher(create)

    async def scenario() -> None:
        app = MenuApp(_JOBS, switchers=switchers)
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_env_switcher(pilot)
            await pilot.press("down", "enter")  # open the form
            await pilot.pause()
            await pilot.press("escape")  # cancel
            await pilot.pause()

    asyncio.run(scenario())
    assert calls == []
    assert len(switchers["environment"].choices) == 1


def test_create_failure_keeps_the_form_open() -> None:
    """A rejected create (bad label / collision) keeps the form and shows the reason."""
    seen: dict[str, object] = {}

    def create(_label: str) -> CreateOutcome:
        return CreateOutcome(None, "already exists")

    async def scenario() -> None:
        app = MenuApp(_JOBS, switchers=_env_switcher(create))
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_env_switcher(pilot)
            await pilot.press("down", "enter")  # open the form
            await pilot.pause()
            app.screen.query_one("#name", Input).value = "Work"
            await pilot.press("enter")
            await pilot.pause()
            seen["still_on_form"] = bool(app.screen.query("#name"))
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())

    asyncio.run(scenario())
    assert seen["still_on_form"] is True  # did not dismiss
    assert "already exists" in str(seen["detail"])


def test_persona_switcher_has_no_new_row() -> None:
    """A switcher without a create callback (persona) shows no New row."""
    count: dict[str, int] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, switchers=_persona_switcher())
        async with app.run_test(size=(90, 30)) as pilot:
            await pilot.press("down", "down", "enter")  # → Config
            await pilot.press("down", "down", "down", "enter")  # → Persona switcher (row 3)
            await pilot.pause()
            count["rows"] = len(app.screen.query_one("#menu", ListView).query(ListItem))

    asyncio.run(scenario())
    assert count["rows"] == 2  # two personas, no create row
