# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The interactive ``gmlw tui`` menu, as a pure Textual app.

Deliberately free of any use case, port, or composition import: the app navigates menus
and *returns a choice*. It never launches a client itself -- the CLI wiring does that, after
``run()`` returns and the terminal is restored. That separation keeps the risky teardown ->
subprocess hand-off outside the event loop, and keeps this app trivially drivable by
Textual's ``run_test``/``Pilot``.

The structure is object-first (Job / Workflow / Config), then a verb. Job > Resume and the
Config switchers (Persona / Environment / Role, incl. creating one) are wired; the remaining
verbs are placeholders that update the detail panel until they are built out.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, cast

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Input, Label, ListItem, ListView, Static

from generic_ml_wrapper.adapter.inbound.tui.banner import boxed_banner
from generic_ml_wrapper.common import i18n


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
class SwitchChoice:
    """One option in a switcher: the config ``value`` written, plus what the user sees.

    For personas ``value`` and ``label`` are both the persona name; for the folder-backed
    axes ``value`` is the slug (what's stored) and ``label`` is the human name (what's shown).
    """

    value: str
    label: str
    description: str


@dataclass(frozen=True)
class CreateOutcome:
    """The result of a create-from-label attempt handed back by the injected ``create``.

    On success ``choice`` is the new option to add and select; on failure it is ``None``
    (a bad label or a collision) and ``message`` explains why. Either way ``message`` is
    shown in the panel.
    """

    choice: SwitchChoice | None
    message: str


@dataclass
class Switcher:
    """A "pick one, set a config key" screen's data: its rows, current value, and setters.

    Mutable because ``current`` moves as the user switches. ``apply`` persists the chosen
    value; ``create`` (when set) creates a new option from a typed label and makes it
    current. Both are the only outbound calls, injected by the wiring so the app stays free
    of use-case imports. ``create`` is ``None`` for axes that cannot be created (personas).
    """

    crumb: str
    choices: list[SwitchChoice]
    current: str | None
    apply: Callable[[str], str]
    create: Callable[[str], CreateOutcome] | None = None


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


# The object-first menu tree, built through the active localiser. Each entry is
# (icon, title-key, action, example); the subtitle key is the title key + ".d". The
# ``example`` commands stay literal (they are commands, not prose).
_JOB_MENU = (
    ("🆕", "tui.job.new", "job:new", "gmlw start <job>"),
    ("⏵", "tui.job.resume", "job:resume", "gmlw start <job> --resume-latest"),
    ("📋", "tui.job.list", "job:list", "gmlw jobs"),
    ("📊", "tui.job.export", "job:export", "gmlw export <job>"),
)
_WORKFLOW_MENU = (
    ("⏵", "tui.wf.run", "wf:run", "gmlw run <workflow>"),
    ("✨", "tui.wf.create", "wf:create", "gmlw workflow new <name>"),
    ("✏️", "tui.wf.edit", "wf:edit", "gmlw workflow edit <name>"),
    ("📋", "tui.wf.list", "wf:list", "gmlw workflow list"),
)
_CONFIG_MENU = (
    ("📃", "tui.cfg.list", "cfg:list", "gmlw config list"),
    ("🔍", "tui.cfg.get", "cfg:get", "gmlw config get <key>"),
    ("🔧", "tui.cfg.set", "cfg:set", "gmlw config set <key> <value>"),
    ("🎭", "tui.cfg.persona", "cfg:persona", "gmlw config set companion.persona <name>"),
    (
        "🌍",
        "tui.cfg.environment",
        "cfg:environment",
        "gmlw config set profile.default_environment <slug>",
    ),
    ("🎩", "tui.cfg.role", "cfg:role", "gmlw config set profile.default_role <slug>"),
    ("🔌", "tui.cfg.clients", "cfg:clients", "gmlw config set client.default <name>"),
    ("🔁", "tui.cfg.setup", "cfg:setup", "gmlw init"),
)
_TOP_MENU = (
    ("🗂", "tui.job", "menu:job", ""),
    ("⚙", "tui.workflow", "menu:workflow", ""),
    ("🎛", "tui.config", "menu:config", ""),
    ("🚪", "tui.quit", "quit", ""),
)


def _menu(rows: tuple[tuple[str, str, str, str], ...]) -> list[_Item]:
    """Resolve a menu spec into localised rows (subtitle key = title key + ``.d``)."""
    t = i18n.active().t
    return [
        _Item(icon, t(key), t(f"{key}.d"), action, example) for icon, key, action, example in rows
    ]


class _Row(ListItem):
    """A two-line list row: icon + bold title on line one, dim subtitle on line two.

    A single markup ``Label`` (not nested containers) so the row sizes to its two lines --
    nested ``Horizontal``/``Vertical`` default to *filling* the parent, which blows each row
    up to the whole viewport.
    """

    def __init__(self, item: _Item) -> None:
        self._label = Label(self._markup(item.icon, item))
        super().__init__(self._label)
        self.item = item

    @staticmethod
    def _markup(icon: str, item: _Item) -> str:
        return f"{icon}  [b]{item.title}[/b]\n    [dim]{item.subtitle}[/dim]"

    def set_icon(self, icon: str) -> None:
        """Re-render the row's leading icon in place (keeps the list cursor put)."""
        self._label.update(self._markup(icon, self.item))


class _MenuScreen(Screen[None]):
    """A menu screen: a header, a rich list, a live detail panel, and a key-hints bar.

    Subclasses supply the header and rows and override ``handle`` to act on a selection.
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "back", "Back"),
        Binding("q", "quit_app", "Quit"),
    ]
    crumb: ClassVar[str] = "gmlw"
    show_banner: ClassVar[bool] = False
    # A one-shot detail message the next detail-sync shows instead of the cursor's row,
    # then clears -- so a confirmation survives a programmatic cursor move.
    _flash: str | None = None

    @property
    def menu_app(self) -> MenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`MenuApp`."""
        return cast("MenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]

    def menu_items(self) -> list[_Item]:
        """The rows for this screen (overridden by dynamic screens like the job picker)."""
        return []

    def initial_index(self) -> int:
        """Which row starts highlighted (overridden to land on the current value)."""
        return 0

    def header_text(self) -> str:
        """The breadcrumb for this screen (overridden where it is dynamic)."""
        return self.crumb

    def compose(self) -> ComposeResult:
        """Header (banner or breadcrumb), the list, then the docked detail + key bar."""
        if self.show_banner:
            yield Static(boxed_banner(), id="banner")
        else:
            yield Static(self.header_text(), id="crumb")
        items = self.menu_items()
        if items:
            yield ListView(*(_Row(i) for i in items), id="menu", initial_index=self.initial_index())
        else:
            yield Static(i18n.active().t("tui.empty"), id="empty")
        with Container(id="status"):
            yield Static("", id="detail")
            yield Static(i18n.active().t("tui.keys"), id="keys")

    def on_mount(self) -> None:
        """Prime the detail panel; a pending flash confirmation wins after the mount settles."""
        self._sync_detail()
        if self._flash is not None:  # written after the initial-highlight sync, so it survives
            message, self._flash = self._flash, None
            self.call_after_refresh(lambda: self.query_one("#detail", Static).update(message))

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
        self.query_one("#detail", Static).update(i18n.active().t("tui.stub", title=item.title))
        self.menu_app.bell()

    def action_back(self) -> None:
        """Pop back to the previous screen."""
        self.menu_app.pop_screen()

    def action_quit_app(self) -> None:
        """Leave gmlw with no choice."""
        self.menu_app.exit(None)


class TopMenuScreen(_MenuScreen):
    """The front door: Job · Workflow · Config · Quit, under the banner."""

    show_banner = True

    def menu_items(self) -> list[_Item]:
        """The object rows: Job, Workflow, Config, Quit."""
        return _menu(_TOP_MENU)

    def handle(self, item: _Item) -> None:
        """Quit, or open the Job/Workflow/Config sub-menu."""
        if item.action == "quit":
            self.menu_app.exit(None)
        elif item.action == "menu:job":
            self.menu_app.push_screen(JobMenuScreen())
        elif item.action == "menu:workflow":
            self.menu_app.push_screen(WorkflowMenuScreen())
        elif item.action == "menu:config":
            self.menu_app.push_screen(ConfigMenuScreen())

    def action_back(self) -> None:
        """At the front door, Back leaves gmlw (there is nothing to pop to)."""
        self.menu_app.exit(None)


class JobMenuScreen(_MenuScreen):
    """The Job object's verbs. Resume is the one wired to launch."""

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job (localised)."""
        return f"gmlw > {i18n.active().t('tui.job')}"

    def menu_items(self) -> list[_Item]:
        """The Job verbs."""
        return _menu(_JOB_MENU)

    def handle(self, item: _Item) -> None:
        """Resume launches; the other Job verbs are stubbed."""
        if item.action == "job:resume":
            self.menu_app.push_screen(JobPickerScreen())
        else:
            self._stub(item)


class WorkflowMenuScreen(_MenuScreen):
    """The Workflow object's verbs (placeholders until built out)."""

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Workflow (localised)."""
        return f"gmlw > {i18n.active().t('tui.workflow')}"

    def menu_items(self) -> list[_Item]:
        """The Workflow verbs."""
        return _menu(_WORKFLOW_MENU)


class ConfigMenuScreen(_MenuScreen):
    """The Config verbs. The switchers (Persona/Environment/Role) are wired; rest are stubs."""

    # Config verb -> switcher key injected on the app.
    _SWITCHERS: ClassVar[dict[str, str]] = {
        "cfg:persona": "persona",
        "cfg:environment": "environment",
        "cfg:role": "role",
    }

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Config (localised)."""
        return f"gmlw > {i18n.active().t('tui.config')}"

    def menu_items(self) -> list[_Item]:
        """The Config verbs."""
        return _menu(_CONFIG_MENU)

    def handle(self, item: _Item) -> None:
        """A switcher verb opens its picker; the other Config verbs are stubbed."""
        key = self._SWITCHERS.get(item.action)
        if key is not None and key in self.menu_app.switchers:
            self.menu_app.push_screen(SwitcherScreen(key))
        else:
            self._stub(item)


class SwitcherScreen(_MenuScreen):
    """Generic "pick one, set a config key" browser (Persona / Environment / Role).

    A *browser* -- unlike the launchers, it stays in the TUI. Selecting a row calls the
    switcher's injected ``apply`` (which persists the config key), moves the dot in place,
    and confirms in the detail panel. No client is launched; no terminal hand-off. It shows
    each option's ``label`` but sets its ``value`` (slug for the folder-backed axes).
    """

    def __init__(self, key: str) -> None:
        """Bind the screen to one injected switcher by its key."""
        super().__init__()
        self._key = key

    @property
    def _switcher(self) -> Switcher:
        return self.menu_app.switchers[self._key]

    def header_text(self) -> str:
        """The switcher's own breadcrumb (e.g. ``gmlw > Config > Environment``)."""
        return self._switcher.crumb

    def menu_items(self) -> list[_Item]:
        """One row per option (active one dotted), then a "New…" row when creatable."""
        current = self._switcher.current
        items = [
            _Item(
                "●" if c.value == current else "○",
                c.label,
                c.description,
                "switch:set",
                payload=c.value,
            )
            for c in self._switcher.choices
        ]
        if self._switcher.create is not None:
            t = i18n.active().t
            new_row = _Item("➕", t("tui.new"), t("tui.new.d"), "switch:new")  # noqa: RUF001
            items.append(new_row)
        return items

    def initial_index(self) -> int:
        """Open with the cursor on the active option, not the first row."""
        values = [c.value for c in self._switcher.choices]
        current = self._switcher.current
        return values.index(current) if current in values else 0

    def handle(self, item: _Item) -> None:
        """Set the picked value, or open the create form for the "New…" row."""
        if item.action == "switch:new":
            self.menu_app.push_screen(CreateAxisScreen(self._key), self._on_created)
            return
        if item.action != "switch:set":
            return
        switcher = self._switcher
        message = switcher.apply(item.payload)
        switcher.current = item.payload
        self._mark_current()
        self.query_one("#detail", Static).update(f"✓ {message}")

    def _on_created(self, choice: SwitchChoice | None) -> None:
        """A new option came back from the create form: add it and reopen on it.

        Rather than surgically patch the live list (fragile against async mounting), record
        the new option and replace this screen with a fresh switcher, which recomposes from
        the updated data, opens the cursor on the new option, and flashes the confirmation.
        """
        if choice is None:  # cancelled, or the create failed and the user backed out
            return
        switcher = self._switcher
        switcher.choices.append(choice)
        switcher.current = choice.value
        self.menu_app.pop_screen()
        reopened = SwitcherScreen(self._key)
        reopened._flash = i18n.active().t("tui.create.done", label=choice.label)
        self.menu_app.push_screen(reopened)

    def _mark_current(self) -> None:
        """Refresh every option row's dot to reflect the current value (in place)."""
        current = self._switcher.current
        for row in self.query_one("#menu", ListView).query(_Row):
            if row.item.action == "switch:set":
                row.set_icon("●" if row.item.payload == current else "○")


class CreateAxisScreen(Screen["SwitchChoice | None"]):
    """A one-field form: type a name, Enter creates the axis (via the injected ``create``).

    The first text-entry screen in the app. On submit it calls the switcher's ``create``
    callback; on success it dismisses with the new :class:`SwitchChoice` (the parent adds and
    selects it), on failure it shows the reason and lets the user retype. Esc cancels.
    """

    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, key: str) -> None:
        """Bind the form to the switcher it creates into."""
        super().__init__()
        self._key = key

    @property
    def _switcher(self) -> Switcher:
        return cast("MenuApp", self.app).switchers[self._key]  # pyright: ignore[reportUnknownMemberType]

    def compose(self) -> ComposeResult:
        """A breadcrumb, the name input, a status line, and the key hints."""
        t = i18n.active().t
        yield Static(f"{self._switcher.crumb} > {t('tui.new')}", id="crumb")
        yield Input(placeholder=t("tui.create.placeholder"), id="name")
        with Container(id="status"):
            yield Static(t("tui.create.hint"), id="detail")
            yield Static(t("tui.create.keys"), id="keys")

    def on_mount(self) -> None:
        """Focus the input so the user can just start typing."""
        self.query_one("#name", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Create from the typed name; dismiss on success, explain and stay on failure."""
        create = self._switcher.create
        if create is None:
            return
        outcome = create(event.value)
        if outcome.choice is not None:
            self.dismiss(outcome.choice)
        else:  # bad label or a collision -- keep the form so the user can fix it
            self.query_one("#detail", Static).update(f"✗ {outcome.message}")

    def action_cancel(self) -> None:
        """Abandon the form without creating anything."""
        self.dismiss(None)


class JobPickerScreen(_MenuScreen):
    """Resume step: pick a job; selecting one hands the resume choice back to the wiring."""

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job > Resume (localised)."""
        t = i18n.active().t
        return f"gmlw > {t('tui.job')} > {t('tui.job.resume')}"

    def menu_items(self) -> list[_Item]:
        """One row per resumable job, carrying the job id as payload."""
        t = i18n.active().t
        return [
            _Item("⏵", j.job, t("tui.sessions", count=j.session_count), "pick", payload=j.job)
            for j in self.menu_app.jobs
        ]

    def handle(self, item: _Item) -> None:
        """A picked job becomes the resume choice handed back to the wiring."""
        if item.action == "pick":
            self.menu_app.exit(MenuChoice(action="resume", job=item.payload))


class MenuApp(App[MenuChoice | None]):
    """The front-end app. ``run()`` returns a :class:`MenuChoice`, or ``None`` to quit.

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
    #name   { margin: 1 2; }
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
        switchers: dict[str, Switcher] | None = None,
    ) -> None:
        """Bind the injected data the browsers read from and the callbacks they invoke.

        Args:
            jobs: The resumable jobs the Resume picker lists.
            switchers: The config switchers, keyed by ``persona`` / ``environment`` /
                ``role``. Each carries its options, current value, and a setter. A missing
                key just leaves that Config verb stubbed, so the app runs unwired in tests.
        """
        super().__init__()
        self.jobs = jobs
        self.switchers = switchers or {}

    def on_mount(self) -> None:
        """Open on the top (object) menu."""
        self.push_screen(TopMenuScreen())
