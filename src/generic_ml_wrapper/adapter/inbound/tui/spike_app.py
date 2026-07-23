# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""SPIKE ONLY (branch ``spike/tui-handoff``): the interactive menu, as a pure Textual app.

Deliberately free of any use case, port, or composition import: the app navigates menus
and *returns a choice*. It never launches a client itself -- the wiring does that, after
``run()`` returns and the terminal is restored. That separation is the whole point of the
spike: the risky teardown -> subprocess hand-off lives outside the event loop, and this app
stays trivially drivable by Textual's ``run_test``/``Pilot``.

The structure is object-first (Job / Workflow / Config), then a verb -- the IA we agreed on.
Only the Job > Resume path is wired to actually launch; every other verb is a stub that
updates the detail panel, so the shape and feel are real without the plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, cast

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static

from generic_ml_wrapper.adapter.inbound.tui.banner import boxed_banner

_KEYS = "↑↓ move · ⏎ select · Esc back · q quit"


def _no_wiring_set_persona(name: str) -> str:
    """Default persona setter when the app runs unwired (tests / bare construction)."""
    return f"(spike) would set persona to '{name}'"


@dataclass(frozen=True)
class MenuChoice:
    """What the user asked the app to do, handed back to the wiring on exit.

    Only ``"resume"`` is produced today (with ``job`` set). A ``None`` return from the app
    (Quit / Ctrl+C) means "do nothing".
    """

    action: str
    job: str | None = None


@dataclass(frozen=True)
class JobChoice:
    """A job the user can resume, plus how many sessions it has (for display)."""

    job: str
    session_count: int


@dataclass(frozen=True)
class PersonaChoice:
    """A selectable persona: its name (the config value) and one-line description."""

    name: str
    description: str


@dataclass(frozen=True)
class _Item:
    """One menu row: an icon, a bold title, a dim subtitle, and what it does.

    ``action`` drives the screen's ``handle``; ``example`` is the equivalent CLI shown in
    the detail panel; ``payload`` carries data a dynamic row needs (e.g. a job id).
    """

    icon: str
    title: str
    subtitle: str
    action: str
    example: str = ""
    payload: str = ""


# The object-first menu tree. Sub-menu verbs share one vocabulary (New/Run/List/Export).
_JOB_MENU = [
    _Item("🆕", "New", "Start a fresh session on a job", "job:new", "gmlw start <job>"),
    _Item(
        "⏵",
        "Resume",
        "Relaunch a job's latest session",
        "job:resume",
        "gmlw start <job> --resume-latest",
    ),
    _Item("📋", "List", "Browse jobs and their sessions", "job:list", "gmlw jobs"),
    _Item("📊", "Export", "Usage and cost for a job", "job:export", "gmlw export <job>"),
]
_WORKFLOW_MENU = [
    _Item(
        "⏵", "Run", "Run a workflow (the job is named after it)", "wf:run", "gmlw run <workflow>"
    ),
    _Item("✨", "Create", "Author a new workflow", "wf:create", "gmlw workflow new <name>"),
    _Item("✏️", "Edit", "Edit an existing workflow", "wf:edit", "gmlw workflow edit <name>"),
    _Item("📋", "List", "Browse the runnable workflows", "wf:list", "gmlw workflow list"),
]
_CONFIG_MENU = [
    _Item("📃", "List", "Show every setting and its value", "cfg:list", "gmlw config list"),
    _Item(
        "🔍", "Get", "Read one setting (type to filter keys)", "cfg:get", "gmlw config get <key>"
    ),
    _Item(
        "🔧",
        "Set",
        "Change one setting (type to filter keys)",
        "cfg:set",
        "gmlw config set <key> <value>",
    ),
    _Item(
        "🎭",
        "Persona",
        "Choose the companion persona (from a labelled list)",
        "cfg:persona",
        "gmlw config set companion.persona <name>",
    ),
    _Item(
        "🌍",
        "Environment",
        "Switch the active environment (by label)",
        "cfg:environment",
        "gmlw config set profile.default_environment <slug>",
    ),
    _Item(
        "🎩",
        "Role",
        "Switch the active role (by label)",
        "cfg:role",
        "gmlw config set profile.default_role <slug>",
    ),
    _Item(
        "🔌",
        "Clients",
        "Installed clients and their versions",
        "cfg:clients",
        "gmlw config set client.default <name>",
    ),
    _Item("🔁", "Setup", "Re-run the first-time setup", "cfg:setup", "gmlw init"),
]
_TOP_MENU = [
    _Item("🗂", "Job", "Start, resume, and inspect your jobs", "menu:job"),
    _Item("⚙", "Workflow", "Author and run reusable procedures", "menu:workflow"),
    _Item("🎛", "Config", "Settings, clients, personas, environments", "menu:config"),
    _Item("🚪", "Quit", "Leave gmlw", "quit"),
]


class _Row(ListItem):
    """A two-line list row: icon + bold title on line one, dim subtitle on line two.

    A single markup ``Label`` (not nested containers) so the row sizes to its two lines --
    nested ``Horizontal``/``Vertical`` default to *filling* the parent, which blows each row
    up to the whole viewport.
    """

    def __init__(self, item: _Item) -> None:
        super().__init__(Label(f"{item.icon}  [b]{item.title}[/b]\n    [dim]{item.subtitle}[/dim]"))
        self.item = item


class _SpikeScreen(Screen[None]):
    """A menu screen: a header, a rich list, a live detail panel, and a key-hints bar.

    Subclasses supply the header and rows and override ``handle`` to act on a selection.
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "back", "Back"),
        Binding("q", "quit_app", "Quit"),
    ]
    crumb: ClassVar[str] = "gmlw"
    show_banner: ClassVar[bool] = False

    @property
    def spike_app(self) -> SpikeMenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`SpikeMenuApp`."""
        return cast("SpikeMenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]

    def menu_items(self) -> list[_Item]:
        """The rows for this screen (overridden by dynamic screens like the job picker)."""
        return []

    def compose(self) -> ComposeResult:
        """Header (banner or breadcrumb), the list, then the docked detail + key bar."""
        if self.show_banner:
            yield Static(boxed_banner(), id="banner")
        else:
            yield Static(self.crumb, id="crumb")
        items = self.menu_items()
        if items:
            yield ListView(*(_Row(i) for i in items), id="menu")
        else:
            yield Static("Nothing here yet.", id="empty")
        with Container(id="status"):
            yield Static("", id="detail")
            yield Static(_KEYS, id="keys")

    def on_mount(self) -> None:
        """Prime the detail panel for the first highlighted row."""
        self._sync_detail()

    def on_list_view_highlighted(self, _event: ListView.Highlighted) -> None:
        """Follow the cursor: show the highlighted row's description and CLI equivalent."""
        self._sync_detail()

    def _sync_detail(self) -> None:
        item = self._highlighted()
        if item is None:
            return
        text = item.subtitle if not item.example else f"{item.subtitle}\n$ {item.example}"
        self.query_one("#detail", Static).update(text)

    def _highlighted(self) -> _Item | None:
        try:
            row = self.query_one("#menu", ListView).highlighted_child
        except Exception:  # noqa: BLE001  no list on this screen (empty state)
            return None
        return row.item if isinstance(row, _Row) else None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Dispatch the chosen row to the screen's handler."""
        event.stop()
        if isinstance(event.item, _Row):
            self.handle(event.item.item)

    def handle(self, item: _Item) -> None:
        """Act on a selected row. Base behaviour: flag it as not wired, and beep."""
        self._stub(item)

    def _stub(self, item: _Item) -> None:
        self.query_one("#detail", Static).update(
            f"'{item.title}' isn't wired in this spike — try Job > Resume (the live path)."
        )
        self.spike_app.bell()

    def action_back(self) -> None:
        """Pop back to the previous screen."""
        self.spike_app.pop_screen()

    def action_quit_app(self) -> None:
        """Leave gmlw with no choice."""
        self.spike_app.exit(None)


class TopMenuScreen(_SpikeScreen):
    """The front door: Job · Workflow · Config · Quit, under the banner."""

    show_banner = True

    def menu_items(self) -> list[_Item]:
        """The object rows: Job, Workflow, Config, Quit."""
        return _TOP_MENU

    def handle(self, item: _Item) -> None:
        """Quit, or open the Job/Workflow/Config sub-menu."""
        if item.action == "quit":
            self.spike_app.exit(None)
        elif item.action == "menu:job":
            self.spike_app.push_screen(JobMenuScreen())
        elif item.action == "menu:workflow":
            self.spike_app.push_screen(WorkflowMenuScreen())
        elif item.action == "menu:config":
            self.spike_app.push_screen(ConfigMenuScreen())

    def action_back(self) -> None:
        """At the front door, Back leaves gmlw (there is nothing to pop to)."""
        self.spike_app.exit(None)


class JobMenuScreen(_SpikeScreen):
    """The Job object's verbs. Resume is the one wired to launch."""

    crumb = "gmlw > Job"

    def menu_items(self) -> list[_Item]:
        """The Job verbs."""
        return _JOB_MENU

    def handle(self, item: _Item) -> None:
        """Resume launches; the other Job verbs are stubbed."""
        if item.action == "job:resume":
            self.spike_app.push_screen(JobPickerScreen())
        else:
            self._stub(item)


class WorkflowMenuScreen(_SpikeScreen):
    """The Workflow object's verbs (all stubbed in the spike)."""

    crumb = "gmlw > Workflow"

    def menu_items(self) -> list[_Item]:
        """The Workflow verbs."""
        return _WORKFLOW_MENU


class ConfigMenuScreen(_SpikeScreen):
    """The Config verbs. Persona is wired (a browser that mutates); the rest are stubs."""

    crumb = "gmlw > Config"

    def menu_items(self) -> list[_Item]:
        """The Config verbs."""
        return _CONFIG_MENU

    def handle(self, item: _Item) -> None:
        """Persona opens the switcher; the other Config verbs are stubbed."""
        if item.action == "cfg:persona":
            self.spike_app.push_screen(PersonaPickerScreen())
        else:
            self._stub(item)


class PersonaPickerScreen(_SpikeScreen):
    """Switch the companion persona: pick one and the config key is written in place.

    A *browser* screen -- unlike the launchers, it stays in the TUI. Selecting a persona
    calls the injected setter (which persists ``companion.persona``), marks it current, and
    confirms in the detail panel. No client is launched; no terminal hand-off.
    """

    crumb = "gmlw > Config > Persona"

    def menu_items(self) -> list[_Item]:
        """One row per persona; the active one is marked with a filled dot."""
        current = self.spike_app.current_persona
        return [
            _Item(
                "●" if p.name == current else "○",
                p.name,
                p.description,
                "persona:set",
                payload=p.name,
            )
            for p in self.spike_app.personas
        ]

    def handle(self, item: _Item) -> None:
        """Persist the picked persona, refresh the dots, and confirm in the detail panel."""
        if item.action != "persona:set":
            return
        message = self.spike_app.set_persona(item.payload)
        menu = self.query_one("#menu", ListView)
        menu.clear()
        menu.extend(_Row(i) for i in self.menu_items())
        # After the rebuild settles (and its highlight event fires), show the confirmation
        # so it is not overwritten by the follow-the-cursor detail sync.
        self.call_after_refresh(lambda: self.query_one("#detail", Static).update(f"✓ {message}"))


class JobPickerScreen(_SpikeScreen):
    """Resume step: pick a job; selecting one hands the resume choice back to the wiring."""

    crumb = "gmlw > Job > Resume"

    def menu_items(self) -> list[_Item]:
        """One row per resumable job, carrying the job id as payload."""
        return [
            _Item("⏵", j.job, f"{j.session_count} sessions", "pick", payload=j.job)
            for j in self.spike_app.jobs
        ]

    def handle(self, item: _Item) -> None:
        """A picked job becomes the resume choice handed back to the wiring."""
        if item.action == "pick":
            self.spike_app.exit(MenuChoice(action="resume", job=item.payload))


class SpikeMenuApp(App[MenuChoice | None]):
    """The spike front-end. ``run()`` returns a :class:`MenuChoice`, or ``None`` to quit.

    The job list is injected (not read from a store) so the app has no outbound dependency
    and tests can drive it with a fixture list.
    """

    # A calm, mostly-transparent look: no filled bars, and a *subtle* row highlight (the
    # default full-strength accent was the "whole screen in blue"). Rows are two lines and
    # size to content -- never fill the viewport.
    CSS = """
    Screen  { background: $background; }
    #banner { color: cyan; text-style: bold; padding: 1 1 0 1; height: auto; }
    #crumb  { dock: top; padding: 0 1; color: $text-muted; }
    #menu   { height: 1fr; background: transparent; }
    #empty  { height: 1fr; padding: 1 2; color: $text-muted; }
    #status { dock: bottom; height: auto; }
    #detail { padding: 1 1; min-height: 2; height: auto; color: $text-muted; }
    #keys   { padding: 0 1; color: $text-muted; }
    ListItem { height: auto; padding: 0 1; background: transparent; }
    ListView > ListItem.-highlight { background: cyan 15%; }
    ListView:focus > ListItem.-highlight { background: cyan 25%; color: $text; }
    """
    TITLE = "gmlw"

    def __init__(
        self,
        jobs: list[JobChoice],
        *,
        personas: list[PersonaChoice] | None = None,
        current_persona: str | None = None,
        set_persona: Callable[[str], str] | None = None,
    ) -> None:
        """Bind the injected data the browsers read from and the callbacks they invoke.

        Args:
            jobs: The resumable jobs the Resume picker lists.
            personas: The selectable personas the Persona switcher lists.
            current_persona: The persona currently set (``None`` when unset).
            set_persona: Persists a chosen persona and returns a confirmation message;
                a no-op default keeps the app runnable/testable without wiring.
        """
        super().__init__()
        self.jobs = jobs
        self.personas = personas or []
        self.current_persona = current_persona
        self._set_persona = set_persona or _no_wiring_set_persona

    def set_persona(self, name: str) -> str:
        """Persist the chosen persona via the injected setter and mark it current."""
        message = self._set_persona(name)
        self.current_persona = name
        return message

    def on_mount(self) -> None:
        """Open on the top (object) menu."""
        self.push_screen(TopMenuScreen())
