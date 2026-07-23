# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SPIKE ONLY (branch ``spike/tui-handoff``): the interactive menu, as a pure Textual app.

This module is deliberately free of any use case, port, or composition import: the app
navigates menus and *returns a choice*. It never launches a client itself -- the wiring
does that, after ``run()`` has returned and the terminal is restored. That separation is
the whole point of the spike: the risky teardown -> subprocess hand-off lives outside the
event loop, and this app stays trivially drivable by Textual's ``run_test``/``Pilot``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, cast

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Label, ListItem, ListView, Static

from generic_ml_wrapper.adapter.inbound.tui.banner import boxed_banner


@dataclass(frozen=True)
class JobChoice:
    """A job the user picked to resume, plus how many sessions it has (for display)."""

    job: str
    session_count: int


@dataclass(frozen=True)
class MenuChoice:
    """What the user asked the app to do, handed back to the wiring on exit.

    ``action`` is one of ``"resume"``, ``"start"``, or ``"config"``; ``job`` is set only
    for ``"resume"``. A ``None`` return from the app (Quit / Ctrl+C) means "do nothing".
    """

    action: str
    job: str | None = None


# The context/help copy shown for each main-menu row. In the real front-end this comes
# from i18n (en/fr parity); hard-coded here so the spike carries no localisation weight.
_MENU_HELP = {
    "start": "Start a new session on a job — you name it, gmlw launches the client.",
    "resume": "Resume a job's latest session — pick the job, gmlw relaunches its client.",
    "config": "View or change settings — default client, environment, role, persona.",
    "quit": "Leave gmlw.",
}


class _Row(ListItem):
    """A list row carrying the payload the handlers act on (action or job)."""

    def __init__(self, label: str, *, action: str = "", job: str = "") -> None:
        super().__init__(Label(label))
        self.action = action
        self.job = job


class _SpikeScreen(Screen[None]):
    """Base screen with a typed handle to the app, so ``jobs``/``exit`` are known types."""

    @property
    def spike_app(self) -> SpikeMenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`SpikeMenuApp`."""
        return cast("SpikeMenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]


class MenuScreen(_SpikeScreen):
    """The front door: Start · Resume · Config · Quit, with a live help bar."""

    BINDINGS: ClassVar[list[Binding]] = [Binding("q", "quit_app", "Quit")]

    def compose(self) -> ComposeResult:
        """Lay out the banner, the four-row menu, the help bar, and the footer."""
        yield Static(boxed_banner(), id="banner")
        yield ListView(
            _Row("Start a job", action="start"),
            _Row("Resume a job", action="resume"),
            _Row("Config", action="config"),
            _Row("Quit", action="quit"),
            id="menu",
        )
        yield Static(_MENU_HELP["start"], id="help")
        yield Footer()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Keep the help bar in step with the highlighted row."""
        row = event.item
        if isinstance(row, _Row):
            self.query_one("#help", Static).update(_MENU_HELP.get(row.action, ""))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Act on the chosen row: resume opens the picker; quit exits; rest is stubbed."""
        event.stop()
        row = event.item
        if not isinstance(row, _Row):
            return
        if row.action == "quit":
            self.spike_app.exit(None)
        elif row.action == "resume":
            self.spike_app.push_screen(JobPickerScreen())
        else:  # start / config: real in the full front-end, out of scope for the spike
            self.query_one("#help", Static).update(
                f"'{row.action}' is not wired in this spike — Resume is the live path."
            )
            self.spike_app.bell()

    def action_quit_app(self) -> None:
        """Quit binding: leave gmlw with no choice."""
        self.spike_app.exit(None)


class JobPickerScreen(_SpikeScreen):
    """Resume step: pick a job; Enter resumes its latest session, Esc goes back."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "back", "Back"),
        Binding("q", "quit_app", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Lay out the breadcrumb, the job list (or an empty note), help, and footer."""
        yield Static("gmlw > Resume", id="crumb")
        jobs = self.spike_app.jobs
        if jobs:
            yield ListView(
                *(_Row(f"{j.job}  ({j.session_count} sessions)", job=j.job) for j in jobs),
                id="jobs",
            )
            yield Static("Enter: resume latest · Esc: back · q: quit", id="help")
        else:
            yield Static("No jobs recorded yet — start one first.", id="empty")
            yield Static("Esc: back · q: quit", id="help")
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """A job was picked: hand the resume choice back to the wiring and tear down."""
        event.stop()
        row = event.item
        if isinstance(row, _Row) and row.job:
            self.spike_app.exit(MenuChoice(action="resume", job=row.job))

    def action_back(self) -> None:
        """Back binding: pop the picker and return to the main menu."""
        self.spike_app.pop_screen()

    def action_quit_app(self) -> None:
        """Quit binding: leave gmlw with no choice."""
        self.spike_app.exit(None)


class SpikeMenuApp(App[MenuChoice | None]):
    """The spike front-end. ``run()`` returns a :class:`MenuChoice`, or ``None`` to quit.

    The job list is injected (not read from a store) so the app has no outbound
    dependency and tests can drive it with a fixture list.
    """

    CSS = """
    #banner { color: cyan; text-style: bold; padding: 1 1 0 1; height: auto; }
    #crumb  { dock: top; padding: 0 1; color: $text-muted; background: $panel; }
    #help   { dock: bottom; padding: 0 1; color: $text-muted; background: $panel; }
    #empty  { padding: 1 2; }
    ListView { height: 1fr; }
    """
    TITLE = "gmlw"

    def __init__(self, jobs: list[JobChoice]) -> None:
        """Bind the injected job list the resume picker reads from."""
        super().__init__()
        self.jobs = jobs

    def on_mount(self) -> None:
        """Open on the main menu."""
        self.push_screen(MenuScreen())
