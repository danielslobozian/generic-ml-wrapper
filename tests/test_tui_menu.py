# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the object-first ``gmlw tui`` menu (Pilot-driven).

The repo has no pytest-asyncio, so each scenario is wrapped in ``asyncio.run`` -- Textual's
``run_test``/``Pilot`` is the only async surface and needs nothing more than an event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import cast

from textual.pilot import Pilot
from textual.widgets import DataTable, Input, ListItem, ListView, Static

from generic_ml_wrapper.adapter.inbound.tui.menu_app import (
    Archiver,
    ClientChoice,
    ClientRow,
    ConfigCatalog,
    ConfigSetResult,
    ConfigSetting,
    CreateOutcome,
    Deleter,
    ImportAttempt,
    JobChoice,
    MenuApp,
    MenuChoice,
    SessionChoice,
    SwitchChoice,
    Switcher,
    UsageView,
    _Row,
)
from generic_ml_wrapper.application.domain.model.rule_axis import RuleAxis
from generic_ml_wrapper.application.domain.model.rule_group import RuleGroup
from generic_ml_wrapper.application.domain.model.rule_summary import RuleSummary
from generic_ml_wrapper.application.domain.model.workflow import Workflow

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
            await pilot.press("enter")  # New → pick a job, or type a name
            await pilot.pause()
            await pilot.press("enter")  # "Type a new name…" → form
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
            await pilot.press("enter", "enter", "enter")  # Job → New → the name form
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
    """Selecting a job opens its (read-only) session table, one row per session."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, sessions_for=lambda _job: _SESSIONS, current_client="claude")
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_job_list(pilot)
            await pilot.press("enter")  # drill into alpha
            await pilot.pause()
            table = cast("DataTable[str]", app.screen.query_one("#session_table", DataTable))
            seen["rows"] = table.row_count
            seen["cells"] = " | ".join(
                " ".join(table.get_row_at(i)) for i in range(table.row_count)
            )

    asyncio.run(scenario())
    assert seen["rows"] == 3  # one row per session
    cells = str(seen["cells"])
    assert "alpha_001" in cells
    assert "alpha_003" in cells  # newest present
    assert "latest" in cells  # and marked as latest
    assert "/work/a" in cells  # the folder column


def test_job_list_session_view_is_read_only() -> None:
    """Enter on a session row neither launches nor exits the app; Esc walks back out."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, sessions_for=lambda _job: _SESSIONS, current_client="claude")
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_job_list(pilot)
            await pilot.press("enter")  # drill into alpha
            await pilot.pause()
            await pilot.press("enter")  # activate a session row — read-only, must do nothing
            await pilot.pause()
            seen["running"] = app.is_running
            seen["return"] = app.return_value
            seen["on_table"] = bool(app.screen.query("#session_table"))

    asyncio.run(scenario())
    assert seen["running"] is True  # not exited
    assert seen["return"] is None  # no choice handed back
    assert seen["on_table"] is True  # still on the session table


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

_WORKFLOWS = [
    Workflow(slug="nightly-etl", label="Nightly ETL", description="the overnight load"),
    Workflow(slug="release-notes", label="release-notes", description=""),  # legacy: no sidecar
]


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
    # The label leads; a legacy workflow with no sidecar still shows its slug.
    assert seen["titles"] == ["Nightly ETL", "release-notes"]


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
    ClientRow("Claude Code", "1.2.3", "yes", "●", name="claude"),
    ClientRow(
        "OpenAI Codex CLI",
        "not installed",
        "yes",
        "",
        name="codex",
        note="Resumable: once its id is bound, after the first turn",
    ),
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


def test_config_list_shows_a_settings_table() -> None:
    """Config → List renders every setting as a DataTable row (key/value/default/type)."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, config=_config_catalog())
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("down", "down", "enter")  # → Config
            await pilot.press("enter")  # List (row 0)
            await pilot.pause()
            table = cast("DataTable[str]", app.screen.query_one("#settings", DataTable))
            seen["rows"] = table.row_count
            seen["cells"] = " | ".join(
                " ".join(table.get_row_at(i)) for i in range(table.row_count)
            )

    asyncio.run(scenario())
    assert seen["rows"] == len(_SETTINGS)  # one row per setting
    cells = str(seen["cells"])
    assert "logging.level" in cells
    assert "warning" in cells  # the value column


def test_config_list_is_stubbed_when_unwired() -> None:
    """With no config injected, Config → List falls through to the stub."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS)  # no config
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.press("down", "down", "enter")  # → Config
            await pilot.press("enter")  # List (stubbed)
            await pilot.pause()
            seen["has_table"] = bool(app.screen.query("#settings"))
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())

    asyncio.run(scenario())
    assert seen["has_table"] is False
    assert "isn't wired yet" in str(seen["detail"])


# --- Config Setup (re-run init) -----------------------------------------------------------


def test_config_setup_exits_with_the_init_choice() -> None:
    """Config → Setup exits the app with an init choice (the wiring re-runs setup)."""
    result: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS)
        async with app.run_test(size=(90, 30)) as pilot:
            await pilot.press("down", "down", "enter")  # → Config
            # list get set persona environment role clients setup(7)
            await pilot.press("down", "down", "down", "down", "down", "down", "down", "enter")
        result["value"] = app.return_value

    asyncio.run(scenario())
    assert result["value"] == MenuChoice(action="init")


def _rules_app(groups: tuple[RuleGroup, ...]) -> MenuApp:
    """A menu app whose Rules browser reads a fixture catalogue."""
    return MenuApp(_JOBS, rules=lambda: groups)


async def _open_rules(pilot: Pilot[MenuChoice | None]) -> None:
    """Top menu -> Rules (the fourth row, above Quit)."""
    await pilot.press("down", "down", "down", "enter")


def test_rules_menu_is_empty_until_a_rule_exists() -> None:
    """With no rules the browser explains where they come from rather than showing branches."""
    text: dict[str, object] = {}
    app = _rules_app(())

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_rules(pilot)
            text["empty"] = str(app.screen.query_one("#empty", Static).render())

    asyncio.run(scenario())
    assert "captured during a session" in str(text["empty"])


def test_rules_menu_lists_only_axes_that_hold_rules() -> None:
    """A role rule exists and no environment rule does, so only Role is offered."""
    groups = (
        RuleGroup(
            axis=RuleAxis.ROLE,
            slug="software-engineer",
            label="Software engineer",
            rules=(RuleSummary(slug="no-transactional", rule="No @Transactional."),),
        ),
    )
    titles: dict[str, object] = {}
    app = _rules_app(groups)

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_rules(pilot)
            rows = app.screen.query_one("#menu", ListView).query(_Row)
            titles["seq"] = [r.item.title for r in rows]

    asyncio.run(scenario())
    assert titles["seq"] == ["Role"]  # no Environment branch to walk into


def test_walking_to_a_rule_shows_its_text_and_draft_status() -> None:
    """Rules > Role > Software engineer lists the rule; the detail panel shows it."""
    groups = (
        RuleGroup(
            axis=RuleAxis.ROLE,
            slug="software-engineer",
            label="Software engineer",
            rules=(
                RuleSummary(
                    slug="no-transactional",
                    rule="No @Transactional in a use case.",
                    strength="hard",
                    draft=True,
                ),
            ),
        ),
    )
    seen: dict[str, object] = {}
    app = _rules_app(groups)

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_rules(pilot)
            await pilot.press("enter")  # the Role axis
            await pilot.press("enter")  # the Software engineer group
            rows = app.screen.query_one("#menu", ListView).query(_Row)
            seen["titles"] = [r.item.title for r in rows]
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())

    asyncio.run(scenario())
    assert seen["titles"] == ["no-transactional"]
    detail = str(seen["detail"])
    assert "No @Transactional in a use case." in detail
    assert "draft" in detail  # a draft is injected into no session; the browser must say so


# ── workflow export / import ──
_ARCHIVE_WORKFLOWS = [
    Workflow(slug="doc-review", label="Doc Review", description="review the docs"),
    Workflow(slug="nightly-etl", label="Nightly ETL", description=""),
]


class _RecordingArchiver:
    """An Archiver that records what it was asked to do and answers with fixed lines.

    ``clash`` makes the next install report a name collision, so the confirmation branch
    can be driven without a real archive on disk.
    """

    def __init__(self, *, clash: bool = False) -> None:
        self.exported: list[str] = []
        self.installed: list[tuple[str, bool]] = []
        self._clash = clash
        self.catalogue = list(_ARCHIVE_WORKFLOWS)

    def as_archiver(self) -> Archiver:
        return Archiver(
            export=self._export, install=self._install, reload_workflows=lambda: self.catalogue
        )

    def _export(self, slug: str) -> str:
        self.exported.append(slug)
        return f"exported to /tmp/{slug}.zip"

    def _install(self, archive: str, replace: bool) -> ImportAttempt:
        self.installed.append((archive, replace))
        if self._clash and not replace:
            return ImportAttempt("a workflow named 'doc-review' already exists.", True)
        if not Path(archive).expanduser().is_file():
            # What the real closure renders when the import refuses an unreadable archive.
            # The form used to check this itself; the import answers it now.
            return ImportAttempt("✗ no file there")
        self.catalogue = [
            *_ARCHIVE_WORKFLOWS,
            Workflow(slug="fresh", label="Fresh", description=""),
        ]
        return ImportAttempt("workflow 'fresh' imported.")


def _workflow_app(archiver: _RecordingArchiver | None = None) -> MenuApp:
    return MenuApp(
        _JOBS,
        workflows=list(_ARCHIVE_WORKFLOWS),
        archiver=(archiver or _RecordingArchiver()).as_archiver(),
    )


async def _open_workflow_menu(pilot: Pilot[MenuChoice | None]) -> None:
    """Top → Workflow."""
    await pilot.press("down", "enter")
    await pilot.pause()


def test_export_packs_the_picked_workflow_without_leaving_the_list() -> None:
    """Packing a zip asks nothing, so it should not cost the user their place."""
    recorder = _RecordingArchiver()
    app = _workflow_app(recorder)
    seen: dict[str, object] = {}

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_workflow_menu(pilot)
            await pilot.press("down", "down", "down", "down", "enter")  # Export
            await pilot.pause()
            seen["titles"] = [str(r.item.title) for r in app.screen.query(_Row)]
            await pilot.press("enter")  # the first workflow
            await pilot.pause()
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())
            seen["running"] = app.is_running

    asyncio.run(scenario())
    # The picker reads by label, but exports the slug the CLI verb takes.
    assert seen["titles"] == ["Doc Review", "Nightly ETL"]
    assert recorder.exported == ["doc-review"]
    assert "exported to" in str(seen["detail"])  # said in place...
    assert seen["running"] is True  # ...and still on the picker
    assert app.return_value is None


def test_a_second_export_is_one_keypress_away() -> None:
    recorder = _RecordingArchiver()
    app = _workflow_app(recorder)

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_workflow_menu(pilot)
            await pilot.press("down", "down", "down", "down", "enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("down", "enter")
            await pilot.pause()

    asyncio.run(scenario())
    assert recorder.exported == ["doc-review", "nightly-etl"]


async def _submit_archive(app: MenuApp, pilot: Pilot[MenuChoice | None], archive: Path) -> None:
    """Top → Workflow → Import → paste the path → submit."""
    await _open_workflow_menu(pilot)
    await pilot.press("down", "down", "down", "down", "down", "enter")  # Import
    await pilot.pause()
    app.screen.query_one("#archive", Input).value = str(archive)
    await pilot.press("enter")
    await pilot.pause()


def test_import_installs_the_archive_without_leaving_the_menu(tmp_path: Path) -> None:
    archive = tmp_path / "shared.zip"
    archive.write_bytes(b"PK")
    recorder = _RecordingArchiver()
    app = _workflow_app(recorder)
    seen: dict[str, object] = {}

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _submit_archive(app, pilot, archive)
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())
            seen["crumb"] = str(app.screen.query_one("#crumb", Static).render())
            seen["running"] = app.is_running

    asyncio.run(scenario())
    assert recorder.installed == [(str(archive), False)]
    assert "imported" in str(seen["detail"])
    assert "Workflow" in str(seen["crumb"])  # back on the Workflow menu, not the front door
    assert seen["running"] is True
    assert app.return_value is None


def test_a_successful_import_shows_up_in_the_workflow_list(tmp_path: Path) -> None:
    """A workflow you cannot see is one you cannot run — the catalogue has to re-read."""
    archive = tmp_path / "shared.zip"
    archive.write_bytes(b"PK")
    app = _workflow_app()
    seen: dict[str, object] = {}

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _submit_archive(app, pilot, archive)
            # The Workflow menu kept its cursor on Import, where we left it — up twice
            # from there is List (Run, Create, Edit, List, Export, Import).
            await pilot.press("up", "up", "enter")
            await pilot.pause()
            seen["titles"] = [str(r.item.title) for r in app.screen.query(_Row)]

    asyncio.run(scenario())
    assert "Fresh" in str(seen["titles"])


def test_a_name_clash_is_asked_about_in_place(tmp_path: Path) -> None:
    archive = tmp_path / "shared.zip"
    archive.write_bytes(b"PK")
    recorder = _RecordingArchiver(clash=True)
    app = _workflow_app(recorder)
    seen: dict[str, object] = {}

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _submit_archive(app, pilot, archive)
            seen["body"] = str(app.screen.query_one("#consequences", Static).render())
            await pilot.press("down", "enter")  # Yes, replace
            await pilot.pause()

    asyncio.run(scenario())
    assert "already exists" in str(seen["body"])
    assert recorder.installed == [(str(archive), False), (str(archive), True)]


def test_declining_a_clash_leaves_the_existing_workflow_alone(tmp_path: Path) -> None:
    archive = tmp_path / "shared.zip"
    archive.write_bytes(b"PK")
    recorder = _RecordingArchiver(clash=True)
    app = _workflow_app(recorder)

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _submit_archive(app, pilot, archive)
            await pilot.press("escape")  # Esc is a no
            await pilot.pause()

    asyncio.run(scenario())
    assert recorder.installed == [(str(archive), False)]  # never re-run with replace


def test_import_keeps_the_form_open_when_the_archive_is_not_there() -> None:
    # A typo is corrected here rather than tearing the menu down. The check itself is the
    # import's; what this pins is that its refusal leaves the form standing.
    app = _workflow_app()

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_workflow_menu(pilot)
            await pilot.press("down", "down", "down", "down", "down", "enter")
            await pilot.pause()
            app.screen.query_one("#archive", Input).value = "/nope/missing.zip"
            await pilot.press("enter")
            await pilot.pause()
            assert "✗" in str(app.screen.query_one("#detail", Static).render())

    asyncio.run(scenario())
    assert app.return_value is None  # still in the form, nothing handed back


def test_config_picker_highlight_reads_as_selected_while_the_filter_holds_focus() -> None:
    """The first row is really marked, and painted at focused strength, on open and on filter.

    Two failures met here: the rebuild set the index on rows that ``clear()`` was still
    removing, so *no* row ended up marked; and the list never holds focus (the Input does),
    so the highlight would have been painted at the dim, unfocused strength anyway. Either
    one makes the first Down look like it skipped a row.
    """
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, config=_config_catalog())
        async with app.run_test(size=(90, 30)) as pilot:
            await _open_config_get(pilot)
            menu = app.screen.query_one("#menu", ListView)
            row = menu.highlighted_child
            seen["focused_is_input"] = isinstance(app.focused, Input)
            seen["index"] = menu.index
            seen["marked"] = row is not None and row.has_class("-highlight")
            seen["alpha"] = None if row is None else row.styles.background.a
            await pilot.press("l", "o", "g")  # filtering rebuilds the rows: still marked
            await pilot.pause()
            filtered = app.screen.query_one("#menu", ListView).highlighted_child
            seen["marked_after_filter"] = filtered is not None and filtered.has_class("-highlight")

    asyncio.run(scenario())
    assert seen["focused_is_input"] is True  # the filter, not the list, has focus
    assert seen["index"] == 0  # the first row *is* the selection...
    assert seen["marked"] is True  # ...it carries the highlight class...
    assert seen["alpha"] == 0.25  # ...and is painted at focused strength, not the dim 15%
    assert seen["marked_after_filter"] is True


# --- Config Clients: making the highlighted client the default ----------------------------


def _clients_app(
    apply: Callable[[str], ConfigSetResult] | None = None,
) -> MenuApp:
    """A menu wired with the clients view and (unless told otherwise) a default-client setter."""
    return MenuApp(
        _JOBS,
        clients=lambda: _CLIENTS,
        set_default_client=apply or (lambda name: ConfigSetResult(ok=True, message=f"→ {name}")),
        current_client="claude",
    )


async def _load_config_clients(app: MenuApp, pilot: Pilot[MenuChoice | None]) -> DataTable[str]:
    """Open Config → Clients, let the worker land, and hand back the table.

    Nothing here forces focus: the table takes it on mount, which is what makes ↑↓/⏎ reach
    the rows at all — a test that focused it by hand would hide the day that stops being true.
    """
    await _open_config_clients(pilot)
    await _drain_workers(app)
    await pilot.pause()
    return cast("DataTable[str]", app.screen.query_one("#clients", DataTable))


def test_config_clients_enter_makes_the_highlighted_client_the_default() -> None:
    """Enter on a row writes that client as the default and moves the marker onto it."""
    picked: list[str] = []
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _clients_app(lambda name: (picked.append(name), ConfigSetResult(True, "set"))[1])
        async with app.run_test(size=(100, 40)) as pilot:
            table = await _load_config_clients(app, pilot)
            seen["focused_is_table"] = app.focused is table  # the keys reach the rows unaided
            await pilot.press("down", "enter")  # the second row: codex
            await pilot.pause()
            seen["was"] = list(table.get_row_at(0))[3]  # claude's marker cell, now cleared
            seen["now"] = list(table.get_row_at(1))[3]  # codex's, now marked
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())
            seen["current"] = app.current_client

    asyncio.run(scenario())
    assert seen["focused_is_table"] is True
    assert picked == ["codex"]  # the client *id*, not the display name
    assert seen["was"] == ""  # the marker moved rather than being duplicated
    assert seen["now"] == "●"
    assert "✓" in str(seen["detail"])
    assert seen["current"] == "codex"  # so the resume picker's "will launch on" notes stay true


def test_config_clients_keeps_the_marker_when_the_set_is_rejected() -> None:
    """A refused value explains itself and changes nothing (defensive: the rows are valid)."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _clients_app(lambda _name: ConfigSetResult(ok=False, message="nope"))
        async with app.run_test(size=(100, 40)) as pilot:
            table = await _load_config_clients(app, pilot)
            await pilot.press("down", "enter")
            await pilot.pause()
            seen["marker"] = list(table.get_row_at(0))[3]
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())
            seen["current"] = app.current_client

    asyncio.run(scenario())
    assert seen["marker"] == "●"  # untouched
    assert "✗ nope" in str(seen["detail"])
    assert seen["current"] == "claude"


def test_config_clients_stays_read_only_without_a_setter() -> None:
    """Wired for viewing only: Enter does nothing, and the key bar never offers the switch."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS, clients=lambda: _CLIENTS, current_client="claude")  # no setter
        async with app.run_test(size=(100, 40)) as pilot:
            table = await _load_config_clients(app, pilot)
            await pilot.press("down", "enter")
            await pilot.pause()
            seen["marker"] = list(table.get_row_at(0))[3]
            seen["keys"] = str(app.screen.query_one("#keys", Static).render())
            seen["current"] = app.current_client

    asyncio.run(scenario())
    assert seen["marker"] == "●"  # nothing moved
    assert "default" not in str(seen["keys"])  # the hint bar promises only scrolling + back
    assert seen["current"] == "claude"


def test_config_clients_shows_the_resume_caveat_for_the_cursored_row() -> None:
    """A qualified resume answer explains itself in the detail line, not in the cell."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _clients_app()
        async with app.run_test(size=(100, 40)) as pilot:
            table = await _load_config_clients(app, pilot)
            detail = app.screen.query_one("#detail", Static)
            seen["claude_cell"] = list(table.get_row_at(0))[2]
            seen["claude_note"] = str(detail.render())  # unconditional: nothing to explain
            await pilot.press("down")  # onto codex
            await pilot.pause()
            seen["codex_cell"] = list(table.get_row_at(1))[2]
            seen["codex_note"] = str(detail.render())

    asyncio.run(scenario())
    assert seen["claude_cell"] == "yes"
    assert seen["claude_note"] == ""
    assert seen["codex_cell"] == "yes"  # the column stays a clean yes...
    assert "once its id is bound" in str(seen["codex_note"])  # ...the caveat is below it


# --------------------------------------------------------------------------- #
# Job > Delete                                                                 #
# --------------------------------------------------------------------------- #

_DELETE_SESSIONS = [
    SessionChoice("alpha_001", "claude", "/work/a", True, "2026-07-24 09:00", False, "empty"),
    SessionChoice(
        "alpha_002", "codex", "/work/b", False, "2026-07-24 10:00", False, "12 turn(s) $1.50"
    ),
    SessionChoice("alpha_003", "cursor", "/work/c", True, "2026-07-24 11:00", True, "empty"),
]


class _RecordingDeleter:
    """A Deleter whose removals are recorded, and reflected in the lists it feeds.

    It really does drop what it is told to, because the point of most of these tests is
    what the *next* screen shows — a delete the list does not notice is the bug the
    in-app flow exists to avoid.
    """

    def __init__(self) -> None:
        self.jobs = {"alpha": 3, "beta": 1}
        self.sessions = {j.session_id: j for j in _DELETE_SESSIONS}
        self.deleted_jobs: list[tuple[str, ...]] = []
        self.deleted_sessions: list[tuple[str, tuple[str, ...]]] = []

    def as_deleter(self) -> Deleter:
        return Deleter(
            preview_jobs=lambda picked: "would remove: " + ", ".join(picked),
            delete_jobs=self._delete_jobs,
            preview_sessions=lambda job, picked: f"would remove from {job}: " + ", ".join(picked),
            delete_sessions=self._delete_sessions,
        )

    def _delete_jobs(self, picked: tuple[str, ...]) -> str:
        self.deleted_jobs.append(picked)
        for job in picked:
            self.jobs.pop(job, None)
        return f"removed {len(picked)} job(s)."

    def _delete_sessions(self, job: str, picked: tuple[str, ...]) -> str:
        self.deleted_sessions.append((job, picked))
        for session in picked:
            self.sessions.pop(session, None)
        return f"removed {len(picked)} session(s)."

    def job_choices(self) -> list[JobChoice]:
        return [JobChoice(job=j, session_count=n) for j, n in self.jobs.items()]

    def sessions_for(self, _job: str) -> list[SessionChoice]:
        return [s for s in _DELETE_SESSIONS if s.session_id in self.sessions]


def _delete_app(recorder: _RecordingDeleter | None = None) -> MenuApp:
    rec = recorder or _RecordingDeleter()
    return MenuApp(
        rec.job_choices(),
        sessions_for=rec.sessions_for,
        current_client="claude",
        deleter=rec.as_deleter(),
        reload_jobs=rec.job_choices,
    )


async def _open_delete_menu(pilot: Pilot[MenuChoice | None]) -> None:
    """Top → Job → Delete."""
    await pilot.press("enter")  # Job menu
    await pilot.press("down", "down", "down", "down", "enter")  # Delete (5th verb)
    await pilot.pause()


def _icons(app: MenuApp) -> list[str]:
    """The leading icon of every row, read back off the rendered labels."""
    rows = app.screen.query(ListView).first().query(ListItem)
    return [str(cast(_Row, row)._label.render()).strip()[0] for row in rows]


def _confirm_body(app: MenuApp) -> str:
    """The consequences block the confirmation screen is showing."""
    return str(app.screen.query_one("#consequences", Static).render())


def _detail(app: MenuApp) -> str:
    return str(app.screen.query_one("#detail", Static).render())


def _crumb(app: MenuApp) -> str:
    return str(app.screen.query_one("#crumb", Static).render())


async def _tick_first_job(pilot: Pilot[MenuChoice | None]) -> None:
    """Delete menu → Jobs → tick the first row → ⏎ (opens the confirmation)."""
    await _open_delete_menu(pilot)
    await pilot.press("enter")  # Jobs
    await pilot.pause()
    await pilot.press("space")
    await pilot.press("enter")
    await pilot.pause()


async def _tick_first_session(pilot: Pilot[MenuChoice | None]) -> None:
    """Delete menu → Sessions → pick alpha → tick the first session → ⏎."""
    await _open_delete_menu(pilot)
    await pilot.press("down", "enter")  # Sessions → job picker
    await pilot.pause()
    await pilot.press("enter")  # alpha
    await pilot.pause()
    await pilot.press("space")
    await pilot.press("enter")
    await pilot.pause()


def test_delete_menu_offers_both_grains() -> None:
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _delete_app()
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_delete_menu(pilot)
            seen["rows"] = " ".join(
                str(cast(_Row, row)._label.render())
                for row in app.screen.query(ListView).first().query(ListItem)
            )

    asyncio.run(scenario())
    assert "Jobs" in str(seen["rows"])
    assert "Sessions" in str(seen["rows"])


def test_enter_asks_before_removing_anything() -> None:
    recorder = _RecordingDeleter()
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _delete_app(recorder)
        async with app.run_test(size=(100, 30)) as pilot:
            await _tick_first_job(pilot)
            seen["body"] = _confirm_body(app)
            seen["warning"] = _detail(app)
            seen["running"] = app.is_running

    asyncio.run(scenario())
    assert "would remove: alpha" in str(seen["body"])  # the footprint, on screen
    assert "cannot be undone" in str(seen["warning"])
    assert seen["running"] is True  # the app never left
    assert recorder.deleted_jobs == []  # and nothing has gone yet


def test_the_confirmation_opens_on_the_safe_answer() -> None:
    """⏎ is the most reflexive key there is; it must not be the destructive one."""
    recorder = _RecordingDeleter()

    async def scenario() -> None:
        app = _delete_app(recorder)
        async with app.run_test(size=(100, 30)) as pilot:
            await _tick_first_job(pilot)
            await pilot.press("enter")  # take whatever the cursor started on
            await pilot.pause()

    asyncio.run(scenario())
    assert recorder.deleted_jobs == []


def test_confirming_removes_the_selection() -> None:
    recorder = _RecordingDeleter()

    async def scenario() -> None:
        app = _delete_app(recorder)
        async with app.run_test(size=(100, 30)) as pilot:
            await _tick_first_job(pilot)
            await pilot.press("down", "enter")  # move onto Yes, answer
            await pilot.pause()

    asyncio.run(scenario())
    assert recorder.deleted_jobs == [("alpha",)]


def test_escape_on_the_confirmation_is_a_no() -> None:
    recorder = _RecordingDeleter()

    async def scenario() -> None:
        app = _delete_app(recorder)
        async with app.run_test(size=(100, 30)) as pilot:
            await _tick_first_job(pilot)
            await pilot.press("escape")
            await pilot.pause()

    asyncio.run(scenario())
    assert recorder.deleted_jobs == []


def test_declining_lands_back_on_the_list_with_nothing_to_dismiss() -> None:
    """No acknowledgement for a no: the user knows, and a keypress to clear it is friction."""
    recorder = _RecordingDeleter()
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _delete_app(recorder)
        async with app.run_test(size=(100, 30)) as pilot:
            await _tick_first_job(pilot)
            await pilot.press("escape")
            await pilot.pause()
            seen["crumb"] = _crumb(app)
            seen["detail"] = _detail(app)

    asyncio.run(scenario())
    assert "Jobs" in str(seen["crumb"])  # still on the job-delete list
    assert "removed" not in str(seen["detail"])
    assert "Enter" not in str(seen["detail"])  # nothing to press to carry on


def test_confirming_lands_back_on_the_same_list_not_the_front_door() -> None:
    """The whole point: you stay where you were working, one level deep."""
    recorder = _RecordingDeleter()
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _delete_app(recorder)
        async with app.run_test(size=(100, 30)) as pilot:
            await _tick_first_job(pilot)
            await pilot.press("down", "enter")
            await pilot.pause()
            seen["crumb"] = _crumb(app)
            seen["detail"] = _detail(app)
            seen["rows"] = [
                cast(_Row, row).item.payload
                for row in app.screen.query(ListView).first().query(ListItem)
            ]

    asyncio.run(scenario())
    assert "Delete" in str(seen["crumb"])
    assert "Jobs" in str(seen["crumb"])
    assert "removed 1 job(s)." in str(seen["detail"])  # the outcome, in place
    assert seen["rows"] == ["beta"]  # and the list re-read without the deleted job


def test_a_deleted_session_leaves_the_list_you_are_standing_on() -> None:
    recorder = _RecordingDeleter()
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _delete_app(recorder)
        async with app.run_test(size=(100, 30)) as pilot:
            await _tick_first_session(pilot)
            await pilot.press("down", "enter")
            await pilot.pause()
            seen["crumb"] = _crumb(app)
            seen["rows"] = [
                cast(_Row, row).item.payload
                for row in app.screen.query(ListView).first().query(ListItem)
            ]

    asyncio.run(scenario())
    assert recorder.deleted_sessions == [("alpha", ("alpha_001",))]
    assert "alpha" in str(seen["crumb"])
    assert seen["rows"] == ["alpha_002", "alpha_003"]  # alpha_001 gone, siblings kept


def test_the_tick_state_does_not_survive_a_delete() -> None:
    """A stale tick on a rebuilt list would be a second delete nobody asked for."""
    recorder = _RecordingDeleter()
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _delete_app(recorder)
        async with app.run_test(size=(100, 30)) as pilot:
            await _tick_first_session(pilot)
            await pilot.press("down", "enter")
            await pilot.pause()
            seen["icons"] = _icons(app)

    asyncio.run(scenario())
    assert seen["icons"] == ["☐", "☐"]


def test_clearing_the_last_row_steps_back_out_and_reports_there() -> None:
    """Nothing left to clean means nothing left to stand on."""
    recorder = _RecordingDeleter()
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _delete_app(recorder)
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_delete_menu(pilot)
            await pilot.press("enter")  # Jobs
            await pilot.pause()
            await pilot.press("space", "down", "space")  # tick both jobs
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("down", "enter")  # confirm
            await pilot.pause()
            seen["crumb"] = _crumb(app)
            seen["detail"] = _detail(app)

    asyncio.run(scenario())
    assert recorder.deleted_jobs == [("alpha", "beta")]
    assert "Delete" in str(seen["crumb"])  # back on the Delete menu, not the front door
    assert "removed 2 job(s)." in str(seen["detail"])


def test_ticking_repaints_the_row_and_untick_restores_it() -> None:
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _delete_app()
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_delete_menu(pilot)
            await pilot.press("enter")  # Jobs
            await pilot.pause()
            seen["before"] = _icons(app)
            await pilot.press("space")
            await pilot.pause()
            seen["ticked"] = _icons(app)
            await pilot.press("space")
            await pilot.pause()
            seen["unticked"] = _icons(app)

    asyncio.run(scenario())
    assert seen["before"] == ["☐", "☐"]
    assert seen["ticked"] == ["☑", "☐"]
    assert seen["unticked"] == ["☐", "☐"]


def test_enter_on_an_empty_selection_does_nothing() -> None:
    """The most reflexive key in the app must never delete something nobody ticked."""
    recorder = _RecordingDeleter()
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _delete_app(recorder)
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_delete_menu(pilot)
            await pilot.press("enter")  # Jobs
            await pilot.pause()
            await pilot.press("enter")  # nothing ticked
            await pilot.pause()
            seen["detail"] = _detail(app)
            seen["crumb"] = _crumb(app)

    asyncio.run(scenario())
    assert recorder.deleted_jobs == []
    assert "space" in str(seen["detail"]).lower()  # it says which key ticks a row
    assert "Jobs" in str(seen["crumb"])  # and no confirmation was opened


def test_a_non_resumable_session_is_still_deletable() -> None:
    """This is not the resume picker: a session nobody can reopen is likelier to go."""
    recorder = _RecordingDeleter()

    async def scenario() -> None:
        app = _delete_app(recorder)
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_delete_menu(pilot)
            await pilot.press("down", "enter")
            await pilot.pause()
            await pilot.press("enter")  # alpha
            await pilot.pause()
            await pilot.press("down", "space")  # alpha_002, the non-resumable one
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("down", "enter")  # confirm
            await pilot.pause()

    asyncio.run(scenario())
    assert recorder.deleted_sessions == [("alpha", ("alpha_002",))]


def test_the_session_delete_list_shows_what_each_session_used() -> None:
    """The empty session has to be findable, or the delete is a guess."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _delete_app()
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_delete_menu(pilot)
            await pilot.press("down", "enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            seen["rows"] = " ".join(
                str(cast(_Row, row)._label.render())
                for row in app.screen.query(ListView).first().query(ListItem)
            )

    asyncio.run(scenario())
    assert "empty" in str(seen["rows"])
    assert "12 turn(s) $1.50" in str(seen["rows"])


def test_the_delete_screens_advertise_the_toggle_key() -> None:
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = _delete_app()
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_delete_menu(pilot)
            await pilot.press("enter")
            await pilot.pause()
            seen["keys"] = str(app.screen.query_one("#keys", Static).render())

    asyncio.run(scenario())
    assert "space" in str(seen["keys"])


def test_a_delete_screen_with_no_jobs_says_so() -> None:
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp([])  # nothing has ever been recorded
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_delete_menu(pilot)
            await pilot.press("enter")  # Jobs
            await pilot.pause()
            seen["empty"] = str(app.screen.query_one("#empty", Static).render())

    asyncio.run(scenario())
    assert "Nothing to delete" in str(seen["empty"])


def test_an_unwired_delete_screen_is_inert() -> None:
    """No Deleter injected (tests, or a future caller): ticking and confirming do nothing."""

    async def scenario() -> MenuChoice | None:
        app = MenuApp(_JOBS)
        async with app.run_test(size=(100, 30)) as pilot:
            await _tick_first_job(pilot)
            await pilot.press("down", "enter")
            await pilot.pause()
            assert app.is_running
        return app.return_value

    assert asyncio.run(scenario()) is None


# --------------------------------------------------------------------------- #
# Choosing the client for one launch (#79, #80)                                #
# --------------------------------------------------------------------------- #

_LAUNCH_CLIENTS = [
    ClientChoice("claude", "Claude Code", is_default=True),
    ClientChoice("cursor", "Cursor", is_default=False),
    ClientChoice("cursor-mitm", "cursor-mitm", is_default=False, custom=True),
]


def _launch_app(clients: list[ClientChoice] | None = None) -> MenuApp:
    """An app wired for launching: jobs, workflows, and a client choice."""
    return MenuApp(
        _JOBS,
        workflows=list(_ARCHIVE_WORKFLOWS),
        launch_clients=lambda: list(_LAUNCH_CLIENTS if clients is None else clients),
        current_client="claude",
    )


async def _new_job(pilot: Pilot[MenuChoice | None], name: str = "PROJ-1") -> None:
    """Top → Job → New → "Type a new name…" → type it → submit."""
    await pilot.press("enter")  # Job menu
    await pilot.press("enter")  # New (first verb)
    await pilot.pause()
    await pilot.press("enter")  # the type-a-name row, which is always first
    await pilot.pause()
    cast("MenuApp", pilot.app).screen.query_one("#name", Input).value = name
    await pilot.press("enter")
    await pilot.pause()


def test_starting_a_job_asks_which_client_first() -> None:
    app = _launch_app()
    seen: dict[str, object] = {}

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _new_job(pilot)
            seen["crumb"] = str(app.screen.query_one("#crumb", Static).render())
            seen["titles"] = [r.item.title for r in app.screen.query(_Row)]
            seen["running"] = app.is_running
            await pilot.press("enter")  # take the default
        return app.return_value

    choice = asyncio.run(scenario())
    # The picker is the last screen before something starts, so it still says what.
    assert "Job" in str(seen["crumb"])
    assert "PROJ-1" in str(seen["crumb"])
    assert str(seen["crumb"]).endswith("Client")
    assert seen["titles"] == ["Claude Code", "Cursor", "cursor-mitm"]
    assert seen["running"] is True  # the name step did not launch on its own
    assert choice == MenuChoice(action="start", job="PROJ-1", client="claude")


def test_the_picker_opens_on_the_configured_default() -> None:
    """ "Falling back to the configured client when I do not choose anything" — one keypress."""
    clients = [
        ClientChoice("claude", "Claude Code", is_default=False),
        ClientChoice("cursor", "Cursor", is_default=True),
    ]
    app = _launch_app(clients)

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _new_job(pilot)
            await pilot.press("enter")
        return app.return_value

    assert asyncio.run(scenario()) == MenuChoice(action="start", job="PROJ-1", client="cursor")


def test_a_different_client_can_be_picked_for_one_launch() -> None:
    app = _launch_app()

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _new_job(pilot)
            await pilot.press("down", "enter")  # onto Cursor
        return app.return_value

    choice = asyncio.run(scenario())
    assert choice is not None
    assert choice.client == "cursor"


def test_every_offered_client_is_launchable() -> None:
    """The wiring only offers what can actually run, so no row is a dead end."""
    app = _launch_app()
    seen: dict[str, object] = {}

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _new_job(pilot)
            rows = app.screen.query_one("#menu", ListView).query(ListItem)
            seen["disabled"] = [r.disabled for r in rows]
            seen["icons"] = [r.item.icon for r in app.screen.query(_Row)]

    asyncio.run(scenario())
    assert seen["disabled"] == [False, False, False]
    assert seen["icons"] == ["●", "○", "🔌"]  # default, built-in, your own caller


def test_a_custom_caller_can_be_launched_on_like_any_other() -> None:
    """A [callers] entry gmlw does not ship is a first-class choice, not a footnote."""
    app = _launch_app()

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _new_job(pilot)
            await pilot.press("down", "down", "enter")  # onto cursor-mitm
        return app.return_value

    choice = asyncio.run(scenario())
    assert choice is not None
    assert choice.client == "cursor-mitm"


def test_a_custom_caller_says_where_it_came_from() -> None:
    """No square brackets in strings bound for the detail panel — Rich eats them as markup."""
    app = _launch_app()
    seen: dict[str, object] = {}

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _new_job(pilot)
            await pilot.press("down", "down")  # onto cursor-mitm
            await pilot.pause()
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())

    asyncio.run(scenario())
    assert "your own caller" in str(seen["detail"])
    assert "config.toml" in str(seen["detail"])  # survives Rich's markup parser intact


def test_running_a_workflow_asks_which_client() -> None:
    """Issue #80: a step between picking the workflow and it starting."""
    app = _launch_app()

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_workflow_menu(pilot)
            await pilot.press("enter")  # Run → workflow picker
            await pilot.pause()
            await pilot.press("enter")  # the first workflow
            await pilot.pause()
            await pilot.press("down", "enter")  # Cursor
        return app.return_value

    choice = asyncio.run(scenario())
    assert choice is not None
    assert choice.action == "run"
    assert choice.workflow == "doc-review"
    assert choice.client == "cursor"


def test_the_client_step_names_the_workflow_it_is_about_to_run() -> None:
    app = _launch_app()
    seen: dict[str, object] = {}

    async def scenario() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_workflow_menu(pilot)
            await pilot.press("enter")  # Run
            await pilot.pause()
            await pilot.press("enter")  # doc-review
            await pilot.pause()
            seen["crumb"] = str(app.screen.query_one("#crumb", Static).render())

    asyncio.run(scenario())
    assert "Workflow" in str(seen["crumb"])
    assert "doc-review" in str(seen["crumb"])


def test_authoring_a_new_workflow_asks_after_the_depth() -> None:
    app = _launch_app()

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_workflow_menu(pilot)
            await pilot.press("down", "enter")  # Create
            await pilot.pause()
            app.screen.query_one("#name", Input).value = ""  # unnamed: named at the end
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")  # guided
            await pilot.pause()
            await pilot.press("down", "enter")  # Cursor
        return app.return_value

    choice = asyncio.run(scenario())
    assert choice is not None
    assert choice.action == "workflow_new"
    assert choice.guided is True
    assert choice.client == "cursor"


def test_editing_a_workflow_asks_after_the_depth() -> None:
    app = _launch_app()

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_workflow_menu(pilot)
            await pilot.press("down", "down", "enter")  # Edit → picker
            await pilot.pause()
            await pilot.press("enter")  # the first workflow
            await pilot.pause()
            await pilot.press("down", "enter")  # quick
            await pilot.pause()
            await pilot.press("down", "enter")  # Cursor
        return app.return_value

    choice = asyncio.run(scenario())
    assert choice is not None
    assert choice.action == "workflow_edit"
    assert choice.guided is False
    assert choice.client == "cursor"


def test_resuming_is_not_asked_about() -> None:
    """Issue #79 is explicit: a resumed session already relaunches on its own client."""
    app = MenuApp(
        _JOBS,
        sessions_for=lambda _job: _SESSIONS,
        current_client="claude",
        launch_clients=lambda: list(_LAUNCH_CLIENTS),
    )

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_session_picker(pilot)
            await pilot.press("enter")
        return app.return_value

    choice = asyncio.run(scenario())
    assert choice is not None
    assert choice == MenuChoice(action="resume", job="alpha", session="alpha_003")
    assert choice.client is None  # never asked, never set


def test_escape_backs_out_of_the_client_step_without_launching() -> None:
    app = _launch_app()
    seen: dict[str, object] = {}

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _new_job(pilot)
            await pilot.press("escape")
            await pilot.pause()
            seen["running"] = app.is_running
            seen["crumb"] = str(app.screen.query_one("#crumb", Static).render())
        return app.return_value

    assert asyncio.run(scenario()) is None
    assert seen["running"] is True
    assert "New" in str(seen["crumb"])  # back on the name form


def test_with_no_client_choice_the_launch_goes_straight_through() -> None:
    """Unwired (or nothing detected): no step, and the wiring falls back to the default."""
    app = MenuApp(_JOBS)

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _new_job(pilot)
        return app.return_value

    assert asyncio.run(scenario()) == MenuChoice(action="start", job="PROJ-1", client=None)


# --------------------------------------------------------------------------- #
# Starting a new session on a job you already have (#81)                       #
# --------------------------------------------------------------------------- #


async def _open_new(pilot: Pilot[MenuChoice | None]) -> None:
    """Top → Job → New."""
    await pilot.press("enter")  # Job menu
    await pilot.press("enter")  # New
    await pilot.pause()


def test_new_offers_your_jobs_alongside_typing_a_name() -> None:
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS)
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_new(pilot)
            seen["titles"] = [r.item.title for r in app.screen.query(_Row)]

    asyncio.run(scenario())
    # Typing stays first: it is what the verb says, and the only row on a fresh install.
    assert seen["titles"] == ["Type a new name…", "alpha", "beta"]


def test_picking_an_existing_job_starts_a_session_on_it_without_typing() -> None:
    """The whole issue: the name is already on screen, so it should not be retyped."""
    app = MenuApp(_JOBS)

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_new(pilot)
            await pilot.press("down", "enter")  # alpha
        return app.return_value

    assert asyncio.run(scenario()) == MenuChoice(action="start", job="alpha")


def test_an_existing_job_still_goes_through_the_client_step() -> None:
    """Picking from the list must not skip the choice a typed name gets (#79)."""
    app = _launch_app()

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_new(pilot)
            await pilot.press("down", "enter")  # alpha
            await pilot.pause()
            await pilot.press("down", "enter")  # a different client
        return app.return_value

    choice = asyncio.run(scenario())
    assert choice is not None
    assert choice.job == "alpha"
    assert choice.client == "cursor"


def test_typing_a_brand_new_name_still_works() -> None:
    """The other half of the flow — a job you do not have yet."""
    app = MenuApp(_JOBS, validate_job=_reject_spaces)

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_new(pilot)
            await pilot.press("enter")  # Type a new name…
            await pilot.pause()
            app.screen.query_one("#name", Input).value = "brand-new"
            await pilot.press("enter")
            await pilot.pause()
        return app.return_value

    assert asyncio.run(scenario()) == MenuChoice(action="start", job="brand-new")


def test_with_no_jobs_yet_typing_is_the_only_row() -> None:
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp([])
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_new(pilot)
            seen["titles"] = [r.item.title for r in app.screen.query(_Row)]

    asyncio.run(scenario())
    assert seen["titles"] == ["Type a new name…"]


def test_each_row_shows_the_command_it_is_equivalent_to() -> None:
    """The menu teaches the CLI; a picked job should name the command it stands for."""
    seen: dict[str, object] = {}

    async def scenario() -> None:
        app = MenuApp(_JOBS)
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_new(pilot)
            await pilot.press("down")  # onto alpha
            await pilot.pause()
            seen["detail"] = str(app.screen.query_one("#detail", Static).render())

    asyncio.run(scenario())
    assert "gmlw start alpha" in str(seen["detail"])


def test_escape_from_the_job_choice_returns_to_the_job_menu() -> None:
    seen: dict[str, object] = {}

    async def scenario() -> MenuChoice | None:
        app = MenuApp(_JOBS)
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_new(pilot)
            await pilot.press("escape")
            await pilot.pause()
            seen["crumb"] = str(app.screen.query_one("#crumb", Static).render())
            seen["running"] = app.is_running
        return app.return_value

    assert asyncio.run(scenario()) is None
    assert seen["running"] is True
    assert str(seen["crumb"]).endswith("Job")


def test_resume_is_unchanged_and_still_reopens_a_session() -> None:
    """New and Resume stay different verbs: one starts, one reopens (#81's note)."""
    app = _resume_app()

    async def scenario() -> MenuChoice | None:
        async with app.run_test(size=(100, 30)) as pilot:
            await _open_session_picker(pilot)
            await pilot.press("enter")
        return app.return_value

    assert asyncio.run(scenario()) == MenuChoice(action="resume", job="alpha", session="alpha_003")
