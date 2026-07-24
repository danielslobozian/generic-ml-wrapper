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
    SessionChoice,
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


_SESSIONS = [
    SessionChoice("alpha_001", "claude", "/work/a", True, "2026-07-24 09:00", False),
    SessionChoice("alpha_002", "codex", "/work/b", False, "2026-07-24 10:00", False),
    SessionChoice("alpha_003", "cursor", "/work/c", True, "2026-07-24 11:00", True),
]


def _resume_app() -> MenuApp:
    return MenuApp(_JOBS, sessions_for=lambda _job: _SESSIONS, current_client="claude")


async def _open_session_picker(pilot: Pilot[MenuChoice | None]) -> None:
    """Top → Job → Resume → pick the first job → its session picker."""
    await pilot.press("enter")  # Job menu
    await pilot.press("down", "enter")  # Resume → job picker
    await pilot.press("enter")  # pick first job (alpha) → session picker
    await pilot.pause()


def test_resume_flow_returns_the_chosen_session() -> None:
    """The picker opens on the latest resumable session; Enter resumes that specific one."""
    app = _resume_app()

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_session_picker(pilot)
            await pilot.press("enter")  # the cursor sits on the latest resumable (alpha_003)

    asyncio.run(scenario())
    assert app.return_value == MenuChoice(action="resume", job="alpha", session="alpha_003")


def test_non_resumable_sessions_are_disabled() -> None:
    """The codex session is listed but disabled, so it can't be picked."""
    disabled: dict[str, object] = {}
    app = _resume_app()

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_session_picker(pilot)
            rows = app.screen.query_one("#menu", ListView).query(ListItem)
            disabled["flags"] = [r.disabled for r in rows]

    asyncio.run(scenario())
    assert disabled["flags"] == [False, True, False]  # only the codex row is disabled


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


def _reject_spaces(name: str) -> str | None:
    """A test validator: reject names with spaces (stands in for the JobId pattern)."""
    return "invalid" if " " in name else None


def test_new_job_valid_name_returns_a_start_choice() -> None:
    """Job → New → type a valid name → the app exits with a start choice."""
    result: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, validate_job=_reject_spaces)
        async with app.run_test(size=(90, 30)) as pilot:
            await pilot.press("enter")  # Job menu
            await pilot.press("enter")  # New → form
            await pilot.pause()
            app.screen.query_one("#name", Input).value = "billing-api"
            await pilot.press("enter")
            await pilot.pause()
        result["value"] = app.return_value

    asyncio.run(scenario())
    assert result["value"] == MenuChoice(action="start", job="billing-api")


def test_new_job_invalid_name_keeps_the_form_open() -> None:
    """An unusable name is rejected in-form; the app keeps running (no launch)."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, validate_job=_reject_spaces)
        async with app.run_test(size=(90, 30)) as pilot:
            await pilot.press("enter", "enter")  # Job → New form
            await pilot.pause()
            app.screen.query_one("#name", Input).value = "My Job"
            await pilot.press("enter")
            await pilot.pause()
            seen["running"] = app.is_running
            seen["on_form"] = bool(app.screen.query("#name"))

    asyncio.run(scenario())
    assert seen["running"] is True  # not launched
    assert seen["on_form"] is True  # form still up


def test_new_job_cancel_returns_to_the_job_menu() -> None:
    """Esc in the New form returns to the Job menu without launching."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, validate_job=_reject_spaces)
        async with app.run_test(size=(90, 30)) as pilot:
            await pilot.press("enter", "enter")  # Job → New form
            await pilot.pause()
            await pilot.press("escape")  # cancel
            await pilot.pause()
            seen["running"] = app.is_running
            seen["has_menu"] = bool(app.screen.query("#menu"))  # back on a list screen

    asyncio.run(scenario())
    assert seen["running"] is True
    assert seen["has_menu"] is True
