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
    ConfigCatalog,
    ConfigSetResult,
    ConfigSetting,
    CreateOutcome,
    JobChoice,
    MenuApp,
    MenuChoice,
    SessionChoice,
    SwitchChoice,
    Switcher,
    _Row,
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


def test_session_rows_use_three_state_icons() -> None:
    """Leading icon per state: ▶ resume-on-current, 🔒 non-resumable, ↪ switches client."""
    icons: dict[str, object] = {}
    # default client claude; sessions are claude (current), codex (locked), cursor (switch).
    app = _resume_app()

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_session_picker(pilot)
            rows = app.screen.query_one("#menu", ListView).query(_Row)
            icons["seq"] = [r.item.icon for r in rows]

    asyncio.run(scenario())
    assert icons["seq"] == ["▶", "🔒", "↪"]


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


# --- Config Get / Set (the type-to-filter settings picker + value editors) ---------------

_SETTINGS = [
    ConfigSetting("client.default", "claude", "claude", "str", None, "which client to wrap"),
    ConfigSetting(
        "logging.level",
        "warning",
        "warning",
        "choice",
        ("debug", "info", "warning", "error"),
        "log verbosity",
    ),
    ConfigSetting("hints.show", "true", "true", "bool", None, "show usage hints"),
    ConfigSetting("companion.name", "(unset)", "(unset)", "str?", None, "your name"),
]


def _config_catalog(
    apply: Callable[[str, str], ConfigSetResult] | None = None,
) -> ConfigCatalog:
    """A fresh config catalog (its settings list is mutable -- never share it across tests)."""
    settings = [
        ConfigSetting(s.key, s.value, s.default, s.type_name, s.choices, s.description)
        for s in _SETTINGS
    ]
    return ConfigCatalog(
        crumb="gmlw > Config",
        settings=settings,
        apply=apply or (lambda key, raw: ConfigSetResult(ok=True, message=f"set {key}", value=raw)),
    )


async def _open_config_get(pilot: Pilot[MenuChoice | None]) -> None:
    """Top → Config → Get (Config row index 1)."""
    await pilot.press("down", "down", "enter")  # → Config
    await pilot.press("down", "enter")  # → Get picker
    await pilot.pause()


async def _open_config_set(pilot: Pilot[MenuChoice | None]) -> None:
    """Top → Config → Set (Config row index 2)."""
    await pilot.press("down", "down", "enter")  # → Config
    await pilot.press("down", "down", "enter")  # → Set picker
    await pilot.pause()


def test_config_get_filter_narrows_the_list_by_key() -> None:
    """Typing into the focused filter live-narrows the settings to the matching keys."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, config=_config_catalog())
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_config_get(pilot)
            await pilot.press("l", "o", "g")  # types into the filter (proves it holds focus)
            await pilot.pause()
            seen["keys"] = [r.item.title for r in app.screen.query(_Row)]

    asyncio.run(scenario())
    assert seen["keys"] == ["logging.level"]  # only the key containing "log" survives


def test_config_get_shows_the_value_in_the_detail_panel() -> None:
    """The picker opens on the first setting and its value/default render in the detail panel."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, config=_config_catalog())
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_config_get(pilot)
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())

    asyncio.run(scenario())
    assert "claude" in str(seen["detail"])  # client.default's value/default


def test_config_set_bool_picks_a_value_and_applies_it() -> None:
    """Set → filter to a bool → pick 'false' → the injected apply is called with (key, 'false')."""
    calls: list[tuple[str, str]] = []

    def apply(key: str, raw: str) -> ConfigSetResult:
        calls.append((key, raw))
        return ConfigSetResult(ok=True, message="ok", value=raw)

    async def scenario() -> None:
        app = MenuApp(_JOBS, config=_config_catalog(apply))
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_config_set(pilot)
            await pilot.press("h", "i", "n", "t", "s")  # filter → hints.show (the bool)
            await pilot.pause()
            await pilot.press("enter")  # open the value editor (bool → choice screen)
            await pilot.pause()
            await pilot.press("down", "enter")  # current is 'true' (row 0); pick 'false' (row 1)
            await pilot.pause()

    asyncio.run(scenario())
    assert calls == [("hints.show", "false")]


def test_config_set_choice_picks_from_the_allowed_values() -> None:
    """Set a 'choice' setting: logging.level → 'debug' via the pick-list."""
    calls: list[tuple[str, str]] = []

    def apply(key: str, raw: str) -> ConfigSetResult:
        calls.append((key, raw))
        return ConfigSetResult(ok=True, message="ok", value=raw)

    async def scenario() -> None:
        app = MenuApp(_JOBS, config=_config_catalog(apply))
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_config_set(pilot)
            await pilot.press("l", "o", "g")  # filter → logging.level
            await pilot.pause()
            await pilot.press("enter")  # open the choice screen (opens on 'warning', row 2)
            await pilot.pause()
            await pilot.press("up", "up", "enter")  # warning(2) → info(1) → debug(0)
            await pilot.pause()

    asyncio.run(scenario())
    assert calls == [("logging.level", "debug")]


def test_config_set_str_types_a_value_and_applies_it() -> None:
    """Set a free-text setting: type a value in the input form and submit it."""
    calls: list[tuple[str, str]] = []

    def apply(key: str, raw: str) -> ConfigSetResult:
        calls.append((key, raw))
        return ConfigSetResult(ok=True, message="ok", value=raw)

    async def scenario() -> None:
        app = MenuApp(_JOBS, config=_config_catalog(apply))
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_config_set(pilot)
            await pilot.press("n", "a", "m", "e")  # filter → companion.name (str?)
            await pilot.pause()
            await pilot.press("enter")  # open the input form
            await pilot.pause()
            app.screen.query_one("#value", Input).value = "Ada"
            await pilot.press("enter")  # submit
            await pilot.pause()

    asyncio.run(scenario())
    assert calls == [("companion.name", "Ada")]


def test_config_set_rejected_value_keeps_the_form_and_shows_the_reason() -> None:
    """A rejected set keeps the input form open and surfaces the message."""
    seen: dict[str, object] = {}

    def apply(_key: str, _raw: str) -> ConfigSetResult:
        return ConfigSetResult(ok=False, message="invalid value")

    async def scenario() -> None:
        app = MenuApp(_JOBS, config=_config_catalog(apply))
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_config_set(pilot)
            await pilot.press("c", "l", "i", "e", "n", "t")  # filter → client.default (str)
            await pilot.pause()
            await pilot.press("enter")  # open the input form
            await pilot.pause()
            app.screen.query_one("#value", Input).value = "bogus"
            await pilot.press("enter")  # submit → rejected
            await pilot.pause()
            seen["on_form"] = bool(app.screen.query("#value"))  # form still up
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())

    asyncio.run(scenario())
    assert seen["on_form"] is True
    assert "invalid value" in str(seen["detail"])


def test_config_get_set_are_stubbed_when_unwired() -> None:
    """With no config injected, Config → Get falls through to the stub (no picker opens)."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS)  # no config catalog
        async with app.run_test(size=(90, 30)) as pilot:
            await pilot.press("down", "down", "enter")  # → Config
            await pilot.press("down", "enter")  # → Get (stubbed)
            await pilot.pause()
            seen["has_filter"] = bool(app.screen.query("#filter"))  # no picker mounted
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())

    asyncio.run(scenario())
    assert seen["has_filter"] is False
    assert "isn't wired yet" in str(seen["detail"])


# --- Job List (read-only browse of jobs and their sessions) ------------------------------


async def _open_job_list(pilot: Pilot[MenuChoice | None]) -> None:
    """Top → Job → List (Job row index 2)."""
    await pilot.press("enter")  # → Job menu
    await pilot.press("down", "down", "enter")  # New(0) Resume(1) → List(2)
    await pilot.pause()


def test_job_list_shows_one_row_per_job() -> None:
    """Job → List lists every job with recorded activity."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS)
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_job_list(pilot)
            seen["titles"] = [r.item.title for r in app.screen.query(_Row)]

    asyncio.run(scenario())
    assert seen["titles"] == ["alpha", "beta"]


def test_job_list_drills_into_a_jobs_sessions() -> None:
    """Selecting a job opens its (read-only) session list, one row per session."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, sessions_for=lambda _job: _SESSIONS, current_client="claude")
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_job_list(pilot)
            await pilot.press("enter")  # drill into alpha
            await pilot.pause()
            seen["titles"] = " | ".join(str(r.item.title) for r in app.screen.query(_Row))
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())

    asyncio.run(scenario())
    titles = str(seen["titles"])
    assert "alpha_001" in titles
    assert "alpha_003" in titles  # newest present
    assert "latest" in titles  # and marked as latest
    assert "/work/a" in str(seen["detail"])  # first session's folder in the detail panel


def test_job_list_session_view_is_read_only() -> None:
    """Enter on a session neither launches nor exits the app; Esc walks back out."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, sessions_for=lambda _job: _SESSIONS, current_client="claude")
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_job_list(pilot)
            await pilot.press("enter")  # drill into alpha
            await pilot.pause()
            await pilot.press("enter")  # select a session — read-only, must do nothing
            await pilot.pause()
            seen["running"] = app.is_running
            seen["return"] = app.return_value
            seen["on_sessions"] = bool(app.screen.query("#menu"))

    asyncio.run(scenario())
    assert seen["running"] is True  # not exited
    assert seen["return"] is None  # no choice handed back
    assert seen["on_sessions"] is True  # still on the session list


def test_job_list_empty_when_no_jobs() -> None:
    """With no recorded jobs, Job → List shows the empty state, not a crash."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp([])  # no jobs
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_job_list(pilot)
            seen["rows"] = len(app.screen.query(_Row))
            seen["empty"] = bool(app.screen.query("#empty"))
            seen["running"] = app.is_running

    asyncio.run(scenario())
    assert seen["rows"] == 0
    assert seen["empty"] is True
    assert seen["running"] is True
