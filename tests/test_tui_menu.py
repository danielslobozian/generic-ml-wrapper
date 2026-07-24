# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the object-first ``gmlw tui`` menu (Pilot-driven).

The repo has no pytest-asyncio, so each scenario is wrapped in ``asyncio.run`` -- Textual's
``run_test``/``Pilot`` is the only async surface and needs nothing more than an event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

from textual.pilot import Pilot
from textual.widgets import DataTable, Input, ListItem, ListView, Static

from generic_ml_wrapper.adapter.inbound.tui.menu_app import (
    ClientRow,
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
    UsageView,
    _Row,
)

_JOBS = [JobChoice(job="alpha", session_count=3), JobChoice(job="beta", session_count=1)]


async def _drain_workers(app: MenuApp) -> None:
    """Await all background workers (the Export screens load their report on a worker thread)."""
    await app.workers.wait_for_complete()  # pyright: ignore[reportUnknownMemberType]


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


# --- Job Export v2 (destination chooser, worker-loaded DataTable summary, file save) ------

_USAGE = UsageView(
    job="alpha",
    empty=False,
    summary="3 turns · $1.23",
    model_rows=(("claude", "2", "100", "50", "10", "1.0"), ("codex", "1", "20", "5", "0", "0.5")),
    session_rows=(("alpha_001", "0.80"), ("alpha_002", "0.43")),
)


async def _open_export_dest(pilot: Pilot[MenuChoice | None]) -> None:
    """Top → Job → Export → pick the first job → its destination chooser."""
    await pilot.press("enter")  # → Job menu
    await pilot.press("down", "down", "down", "enter")  # New(0) Resume(1) List(2) → Export(3)
    await pilot.press("enter")  # pick first job (alpha) → destination chooser
    await pilot.pause()


def test_job_export_offers_a_destination_chooser() -> None:
    """Picking a job offers 'view here' and 'save to file' before any (slow) read."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS)
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_export_dest(pilot)
            rows = app.screen.query(_Row)
            seen["count"] = len(rows)
            seen["titles"] = " | ".join(str(r.item.title) for r in rows).lower()

    asyncio.run(scenario())
    assert seen["count"] == 2  # view + file
    assert "file" in str(seen["titles"])


def test_job_export_view_renders_the_summary_tables() -> None:
    """'View' loads the report on a worker and fills the summary + by-model/by-session tables."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, usage_view=lambda _job: _USAGE)
        async with app.run_test(size=(100, 40)) as pilot:
            await _open_export_dest(pilot)
            await pilot.press("enter")  # choose "View summary here"
            await _drain_workers(app)  # await the worker thread
            await pilot.pause()  # let the SUCCESS handler populate the tables
            seen["summary"] = str(app.screen.query_one("#summary", Static).render())
            seen["models"] = app.screen.query_one("#models", DataTable).row_count
            seen["sessions"] = app.screen.query_one("#sessions", DataTable).row_count

    asyncio.run(scenario())
    assert "3 turns" in str(seen["summary"])
    assert seen["models"] == 2  # two model rows
    assert seen["sessions"] == 2  # two session rows


def test_job_export_view_empty_report_has_no_rows() -> None:
    """A job with no usage shows the summary line but no table rows (no crash)."""
    empty = UsageView(job="alpha", empty=True, summary="no usage", model_rows=(), session_rows=())
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, usage_view=lambda _job: empty)
        async with app.run_test(size=(100, 40)) as pilot:
            await _open_export_dest(pilot)
            await pilot.press("enter")  # View
            await _drain_workers(app)
            await pilot.pause()
            seen["models"] = app.screen.query_one("#models", DataTable).row_count
            seen["summary"] = str(app.screen.query_one("#summary", Static).render())

    asyncio.run(scenario())
    assert seen["models"] == 0
    assert "no usage" in str(seen["summary"])


def test_job_export_save_writes_and_shows_the_path() -> None:
    """'Save to file' runs the injected save on a worker and shows the returned path."""
    calls: list[str] = []
    seen: dict[str, object] = {}

    def save(job: str) -> str:
        calls.append(job)
        return "/home/u/.gmlw/exports/alpha-20260724-101500.json"

    async def scenario() -> None:
        app = MenuApp(_JOBS, save_usage=save)
        async with app.run_test(size=(100, 40)) as pilot:
            await _open_export_dest(pilot)
            await pilot.press("down", "enter")  # choose "Save full report to a file"
            await _drain_workers(app)
            await pilot.pause()
            seen["status"] = str(app.screen.query_one("#status_line", Static).render())

    asyncio.run(scenario())
    assert calls == ["alpha"]
    assert "alpha-20260724-101500.json" in str(seen["status"])


def test_job_export_view_is_read_only_and_esc_returns() -> None:
    """The summary view never exits the app; Esc walks back to the destination chooser."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, usage_view=lambda _job: _USAGE)
        async with app.run_test(size=(100, 40)) as pilot:
            await _open_export_dest(pilot)
            await pilot.press("enter")  # View
            await _drain_workers(app)
            await pilot.pause()
            seen["running"] = app.is_running
            await pilot.press("escape")  # back to the chooser
            await pilot.pause()
            seen["return"] = app.return_value
            seen["back_on_chooser"] = bool(app.screen.query("#menu"))

    asyncio.run(scenario())
    assert seen["running"] is True
    assert seen["return"] is None
    assert seen["back_on_chooser"] is True


# --- Workflow Run + List ------------------------------------------------------------------

_WORKFLOWS = ["nightly-etl", "release-notes"]


async def _open_workflow(pilot: Pilot[MenuChoice | None]) -> None:
    """Top → Workflow (2nd object row)."""
    await pilot.press("down", "enter")  # Job(0) → Workflow(1)
    await pilot.pause()


def test_workflow_run_exits_with_the_chosen_workflow() -> None:
    """Workflow → Run → pick a workflow → the app exits with a run choice for it."""
    result: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, workflows=_WORKFLOWS)
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_workflow(pilot)
            await pilot.press("enter")  # Run (row 0) → workflow picker
            await pilot.pause()
            await pilot.press("down", "enter")  # pick the 2nd workflow ('release-notes')
        result["value"] = app.return_value

    asyncio.run(scenario())
    assert result["value"] == MenuChoice(action="run", workflow="release-notes")


def test_workflow_list_shows_the_runnable_workflows() -> None:
    """Workflow → List lists every runnable workflow (read-only)."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, workflows=_WORKFLOWS)
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_workflow(pilot)
            await pilot.press("down", "down", "down", "enter")  # Run(0) Create(1) Edit(2) List(3)
            await pilot.pause()
            seen["titles"] = [str(r.item.title) for r in app.screen.query(_Row)]

    asyncio.run(scenario())
    assert seen["titles"] == _WORKFLOWS


def test_workflow_run_empty_shows_the_create_hint() -> None:
    """With no workflows, the Run picker shows the 'create one' hint, not a crash."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, workflows=[])  # none authored yet
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_workflow(pilot)
            await pilot.press("enter")  # Run → picker
            await pilot.pause()
            seen["rows"] = len(app.screen.query(_Row))
            seen["empty"] = str(app.screen.query_one("#empty", Static).render())

    asyncio.run(scenario())
    assert seen["rows"] == 0
    assert "create" in str(seen["empty"]).lower()


# --- Workflow Create + Edit (name entry + guided/quick authoring depth) --------------------


def test_workflow_create_named_then_guided_exits_with_the_choice() -> None:
    """Workflow → Create → type a name → pick Guided → exits with a guided new-workflow choice."""
    result: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, workflows=_WORKFLOWS)
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_workflow(pilot)
            await pilot.press("down", "enter")  # Create (row 1) → name form
            await pilot.pause()
            app.screen.query_one("#name", Input).value = "etl-nightly"
            await pilot.press("enter")  # → guided chooser
            await pilot.pause()
            await pilot.press("enter")  # pick Guided (row 0)
        result["value"] = app.return_value

    asyncio.run(scenario())
    assert result["value"] == MenuChoice(action="workflow_new", workflow="etl-nightly", guided=True)


def test_workflow_create_empty_name_is_allowed_and_quick() -> None:
    """An empty name is accepted (proposed at the end); Quick sets guided False."""
    result: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, workflows=_WORKFLOWS)
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_workflow(pilot)
            await pilot.press("down", "enter")  # Create → name form
            await pilot.pause()
            await pilot.press("enter")  # empty name → guided chooser
            await pilot.pause()
            await pilot.press("down", "enter")  # pick Quick (row 1)
        result["value"] = app.return_value

    asyncio.run(scenario())
    assert result["value"] == MenuChoice(action="workflow_new", workflow=None, guided=False)


def test_workflow_create_rejects_a_bad_name_and_keeps_the_form() -> None:
    """A non-empty invalid name keeps the form open with the reason (no teardown)."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, validate_workflow=lambda name: "bad name" if name else None)
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_workflow(pilot)
            await pilot.press("down", "enter")  # Create → name form
            await pilot.pause()
            app.screen.query_one("#name", Input).value = "Bad Name!"
            await pilot.press("enter")  # rejected
            await pilot.pause()
            seen["on_form"] = bool(app.screen.query("#name"))
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())
            seen["running"] = app.is_running

    asyncio.run(scenario())
    assert seen["on_form"] is True  # did not tear down
    assert "bad name" in str(seen["detail"])
    assert seen["running"] is True


def test_workflow_edit_picks_a_workflow_then_quick() -> None:
    """Workflow → Edit → pick a workflow → pick Quick → exits with an edit choice."""
    result: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, workflows=_WORKFLOWS)
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_workflow(pilot)
            await pilot.press("down", "down", "enter")  # Edit (row 2) → workflow picker
            await pilot.pause()
            await pilot.press("enter")  # pick 'nightly-etl' → guided chooser
            await pilot.pause()
            await pilot.press("down", "enter")  # pick Quick
        result["value"] = app.return_value

    asyncio.run(scenario())
    assert result["value"] == MenuChoice(
        action="workflow_edit", workflow="nightly-etl", guided=False
    )


# --- Config Clients (worker-loaded DataTable of clients + versions) -----------------------

_CLIENTS = [
    ClientRow("Claude Code", "1.2.3", "yes", "●"),
    ClientRow("OpenAI Codex CLI", "not installed", "no", ""),
]


async def _open_config_clients(pilot: Pilot[MenuChoice | None]) -> None:
    """Top → Config → Clients (Config row index 6)."""
    await pilot.press("down", "down", "enter")  # → Config
    # list get set persona environment role clients(6) setup
    await pilot.press("down", "down", "down", "down", "down", "down", "enter")
    await pilot.pause()


def test_config_clients_loads_a_table_on_a_worker() -> None:
    """Config → Clients loads the clients on a worker and fills the DataTable."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, clients=lambda: _CLIENTS)
        async with app.run_test(size=(100, 40)) as pilot:
            await _open_config_clients(pilot)
            await _drain_workers(app)
            await pilot.pause()
            table = cast("DataTable[str]", app.screen.query_one("#clients", DataTable))
            seen["rows"] = table.row_count
            seen["cells"] = str(list(table.get_row_at(0)))

    asyncio.run(scenario())
    assert seen["rows"] == 2  # one row per supported client
    assert "1.2.3" in str(seen["cells"])  # the version cell rendered


def test_config_clients_is_stubbed_when_unwired() -> None:
    """With no clients injected, Config → Clients falls through to the stub."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS)  # no clients
        async with app.run_test(size=(100, 40)) as pilot:
            await _open_config_clients(pilot)
            seen["has_table"] = bool(app.screen.query("#clients"))
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())

    asyncio.run(scenario())
    assert seen["has_table"] is False  # no screen mounted
    assert "isn't wired yet" in str(seen["detail"])
