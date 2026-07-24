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

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label, ListItem, ListView, Static
from textual.worker import Worker, WorkerState

from generic_ml_wrapper.adapter.inbound.tui.banner import boxed_banner
from generic_ml_wrapper.common import i18n


def _accept_any_job(_name: str) -> str | None:
    """Default new-job-name validator when the app runs unwired (tests): accept anything."""
    return None


def _no_sessions(_job: str) -> list[SessionChoice]:
    """Default session lister when the app runs unwired (tests): no sessions."""
    return []


def _no_usage_view(job: str) -> UsageView:
    """Default usage view when the app runs unwired (tests): an empty report."""
    return UsageView(job=job, empty=True, summary="", model_rows=(), session_rows=())


def _no_save(_job: str) -> str:
    """Default report saver when the app runs unwired (tests): no file written."""
    return ""


@dataclass(frozen=True)
class MenuChoice:
    """What the user asked the app to do, handed back to the wiring on exit.

    ``"resume"`` carries the ``job`` and (from the session picker) the specific ``session``
    to resume. A ``None`` return from the app (Quit / Ctrl+C) means "do nothing".
    """

    action: str
    job: str | None = None
    session: str | None = None


@dataclass(frozen=True)
class JobChoice:
    """A job the user can resume, plus how many sessions it has (for display)."""

    job: str
    session_count: int


@dataclass(frozen=True)
class SessionChoice:
    """A recorded session the resume picker shows: what it was and whether it can resume.

    ``client`` is the client that made it (a resume relaunches on it, not the current
    default); ``cwd`` is the folder it ran in; ``resumable`` gates selection; ``is_latest``
    marks the newest.
    """

    session_id: str
    client: str
    cwd: str | None
    resumable: bool
    date: str
    is_latest: bool


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


@dataclass
class ConfigSetting:
    """One setting the Config Get/Set browsers show: what it is and its current value.

    All display fields are pre-rendered by the wiring (``value``/``default`` already read
    through the CLI's ``_setting_value``), so the app stays free of formatting concerns.
    ``value`` is mutable: a successful set patches it in place so the picker reflects the
    change without a re-read. ``type_name`` (``str`` / ``str?`` / ``bool`` / ``choice``) and
    ``choices`` pick which value editor Set opens.
    """

    key: str
    value: str
    default: str
    type_name: str
    choices: tuple[str, ...] | None
    description: str


@dataclass(frozen=True)
class ConfigSetResult:
    """The outcome of a set attempt handed back by the injected ``apply``.

    ``ok`` is ``False`` for a rejected value (the editor keeps the screen and shows
    ``message``); on success ``value`` is the new rendered value the catalog is patched with.
    Either way ``message`` is the localised line shown to the user.
    """

    ok: bool
    message: str
    value: str = ""


@dataclass
class ConfigCatalog:
    """The settings the Config Get/Set browsers read, plus the setter they call.

    A *browser* bundle, injected by the wiring exactly like :class:`Switcher`: the app reads
    ``settings`` and calls ``apply`` (the only outbound call), so it never imports a use case.
    ``settings`` is mutable — a successful set patches the matching row's value in place.
    """

    crumb: str
    settings: list[ConfigSetting]
    apply: Callable[[str, str], ConfigSetResult]


@dataclass(frozen=True)
class UsageView:
    """A job's usage, pre-rendered for the Export summary view.

    Structured so the screen can lay it out as tables without any formatting logic: ``summary``
    is the totals line (already localised), and ``model_rows``/``session_rows`` are the cells of
    the by-model and by-session-cost tables (all values pre-rendered to strings by the wiring).
    ``empty`` means the job has no recorded usage. The full per-turn detail is deliberately not
    here -- that is what the JSON file export carries.
    """

    job: str
    empty: bool
    summary: str
    model_rows: tuple[tuple[str, ...], ...]
    session_rows: tuple[tuple[str, ...], ...]


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
    note: str = ""  # an extra plain detail line (no "$" prefix), e.g. a resume caveat
    disabled: bool = False  # shown but not selectable (e.g. a non-resumable session)


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
        super().__init__(self._label, disabled=item.disabled)
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
        lines = [item.subtitle]
        if item.example:
            lines.append(f"$ {item.example}")
        if item.note:
            lines.append(item.note)
        self.query_one("#detail", Static).update("\n".join(lines))

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
        """New and Resume launch, List and Export browse; any other Job verb is stubbed."""
        if item.action == "job:resume":
            self.menu_app.push_screen(JobPickerScreen())
        elif item.action == "job:new":
            self.menu_app.push_screen(NewJobScreen())
        elif item.action == "job:list":
            self.menu_app.push_screen(JobListScreen())
        elif item.action == "job:export":
            self.menu_app.push_screen(JobExportScreen())
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

    # Config verb -> the mode its type-to-filter settings picker opens in.
    _PICKERS: ClassVar[dict[str, str]] = {"cfg:get": "get", "cfg:set": "set"}

    def handle(self, item: _Item) -> None:
        """A switcher verb opens its picker, Get/Set the settings picker; the rest are stubs."""
        key = self._SWITCHERS.get(item.action)
        mode = self._PICKERS.get(item.action)
        if key is not None and key in self.menu_app.switchers:
            self.menu_app.push_screen(SwitcherScreen(key))
        elif mode is not None and self.menu_app.config is not None:
            self.menu_app.push_screen(ConfigPickerScreen(mode))
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


class ConfigPickerScreen(_MenuScreen):
    """Type-to-filter the settings, to Get (read) or Set (change) one.

    The app's first live-filtering list: a focused ``Input`` narrows the settings by key as
    you type, while ``↑↓`` move the highlight and ``⏎`` acts on it. A *browser* -- it stays in
    the TUI. In ``get`` mode selecting a row is a no-op (the detail panel already shows the
    setting -- that *is* the read); in ``set`` mode it opens the value editor for the setting's
    type (a pick-list for bool/choice, a text field for strings).
    """

    # The filter Input owns focus so typing always filters; ``q`` must therefore stay typable
    # (no quit binding here). Up/Down/Enter are *priority* bindings so they act on the list
    # before the Input can consume them; printable keys fall through to the Input.
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "back", "Back"),
        Binding("up", "cursor(-1)", "Up", show=False, priority=True),
        Binding("down", "cursor(1)", "Down", show=False, priority=True),
        Binding("enter", "pick", "Select", show=False, priority=True),
    ]

    def __init__(self, mode: str) -> None:
        """Bind the picker to its mode (``"get"`` reads, ``"set"`` changes)."""
        super().__init__()
        self._mode = mode
        self._filter = ""

    @property
    def _config(self) -> ConfigCatalog:
        return cast("ConfigCatalog", self.menu_app.config)  # pushed only when wired

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Config > Get|Set."""
        t = i18n.active().t
        verb = t("tui.cfg.get") if self._mode == "get" else t("tui.cfg.set")
        return f"{self._config.crumb} > {verb}"

    def compose(self) -> ComposeResult:
        """Header, the filter input, the (live) settings list, then detail + key bar."""
        t = i18n.active().t
        yield Static(self.header_text(), id="crumb")
        yield Input(placeholder=t("tui.cfg.filter.placeholder"), id="filter")
        yield ListView(*(_Row(i) for i in self.menu_items()), id="menu")
        with Container(id="status"):
            yield Static("", id="detail")
            yield Static(t("tui.cfg.filter.keys"), id="keys")

    def on_mount(self) -> None:
        """Highlight the first match, prime the detail, and focus the filter for typing."""
        menu = self.query_one("#menu", ListView)
        if menu.children:
            menu.index = 0
        self._sync_detail()
        self.query_one("#filter", Input).focus()

    def menu_items(self) -> list[_Item]:
        """One row per setting whose key contains the filter (case-insensitive; empty = all)."""
        needle = self._filter.lower()
        return [
            _Item("🔧", s.key, s.description, "cfg:pick", payload=s.key, note=self._note(s))
            for s in self._config.settings
            if needle in s.key.lower()
        ]

    @staticmethod
    def _note(setting: ConfigSetting) -> str:
        """The detail line for a setting: current value, default, and any allowed values."""
        t = i18n.active().t
        note = t("tui.cfg.setting", value=setting.value, default=setting.default)
        if setting.choices:
            note += t("tui.cfg.setting.allowed", choices=", ".join(setting.choices))
        return note

    def on_input_changed(self, event: Input.Changed) -> None:
        """Refilter the list as the user types."""
        self._filter = event.value
        self._rebuild()

    def on_screen_resume(self) -> None:
        """Returning from a value editor: rebuild (a set may have changed a value), then flash."""
        self._rebuild()
        if self._flash is not None:  # a confirmation queued by the editor before it popped
            message, self._flash = self._flash, None
            self.call_after_refresh(lambda: self.query_one("#detail", Static).update(message))

    def _rebuild(self) -> None:
        """Rebuild the list rows from the current filter and settings, highlighting the first."""
        menu = self.query_one("#menu", ListView)
        menu.clear()
        items = self.menu_items()
        for item in items:
            menu.append(_Row(item))
        menu.index = 0 if items else None

    def flash(self, message: str) -> None:
        """Queue a one-shot confirmation to show when this picker is next resumed."""
        self._flash = message

    def action_cursor(self, delta: int) -> None:
        """Move the highlight within the filtered list (the Input keeps focus)."""
        menu = self.query_one("#menu", ListView)
        count = len(menu.children)
        if count:
            menu.index = max(0, min(count - 1, (menu.index or 0) + delta))

    def action_pick(self) -> None:
        """Act on the highlighted row (Enter), if any."""
        item = self._highlighted()
        if item is not None:
            self.handle(item)

    def handle(self, item: _Item) -> None:
        """Get: no-op (detail is the read). Set: open the value editor for the setting's type."""
        if item.action != "cfg:pick" or self._mode == "get":
            return
        setting = next((s for s in self._config.settings if s.key == item.payload), None)
        if setting is None:
            return
        if setting.choices is not None or setting.type_name == "bool":
            self.menu_app.push_screen(ConfigChoiceScreen(item.payload))
        else:
            self.menu_app.push_screen(ConfigInputScreen(item.payload))


class ConfigChoiceScreen(_MenuScreen):
    """Set a constrained setting by picking a value: a bool (true/false) or a choice.

    A short dotted list (``●`` current, ``○`` others), like the switchers. Enter applies via
    the injected ``apply``, queues a confirmation on the picker, and pops back to it. A rejected
    value (defensive -- the options are always valid) shows the reason and stays.
    """

    def __init__(self, key: str) -> None:
        """Bind the screen to the setting it sets."""
        super().__init__()
        self._key = key

    @property
    def _config(self) -> ConfigCatalog:
        return cast("ConfigCatalog", self.menu_app.config)

    def _setting(self) -> ConfigSetting:
        return next(s for s in self._config.settings if s.key == self._key)

    def _options(self) -> tuple[str, ...]:
        setting = self._setting()
        return setting.choices if setting.choices is not None else ("true", "false")

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Config > Set > <key>."""
        return f"{self._config.crumb} > {i18n.active().t('tui.cfg.set')} > {self._key}"

    def menu_items(self) -> list[_Item]:
        """One row per allowed value, the current one dotted."""
        current = self._setting().value
        return [
            _Item("●" if value == current else "○", value, "", "choice:set", payload=value)
            for value in self._options()
        ]

    def initial_index(self) -> int:
        """Open the cursor on the current value."""
        options = list(self._options())
        current = self._setting().value
        return options.index(current) if current in options else 0

    def handle(self, item: _Item) -> None:
        """Apply the picked value; on success confirm on the picker and pop, else explain."""
        if item.action != "choice:set":
            return
        result = self._config.apply(self._key, item.payload)
        if not result.ok:
            self.query_one("#detail", Static).update(f"✗ {result.message}")
            return
        self._setting().value = result.value
        below = self.menu_app.screen_stack[-2]
        if isinstance(below, ConfigPickerScreen):
            below.flash(f"✓ {result.message}")
        self.menu_app.pop_screen()


class ConfigInputScreen(Screen[None]):
    """Set a free-text setting (``str`` / ``str?``) by typing a value, modelled on NewJobScreen.

    The current value and default are shown in the hint (an optional ``str?`` can be cleared
    with an empty value or ``none``). Enter applies via the injected ``apply``: on success the
    picker is flashed and this form pops; a rejected value (e.g. an empty required string) keeps
    the form and shows the reason.
    """

    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, key: str) -> None:
        """Bind the form to the setting it sets."""
        super().__init__()
        self._key = key

    @property
    def menu_app(self) -> MenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`MenuApp`."""
        return cast("MenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]

    @property
    def _config(self) -> ConfigCatalog:
        return cast("ConfigCatalog", self.menu_app.config)

    def _setting(self) -> ConfigSetting:
        return next(s for s in self._config.settings if s.key == self._key)

    def compose(self) -> ComposeResult:
        """A breadcrumb, the value input, a status line (current/default hint), and key hints."""
        t = i18n.active().t
        setting = self._setting()
        yield Static(f"{self._config.crumb} > {t('tui.cfg.set')} > {self._key}", id="crumb")
        yield Input(placeholder=t("tui.cfg.value.placeholder"), id="value")
        optional = setting.type_name == "str?"
        hint_key = "tui.cfg.value.hint.optional" if optional else "tui.cfg.value.hint"
        with Container(id="status"):
            yield Static(t(hint_key, value=setting.value, default=setting.default), id="detail")
            yield Static(t("tui.cfg.value.keys"), id="keys")

    def on_mount(self) -> None:
        """Focus the input so the user can just start typing."""
        self.query_one("#value", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Apply the typed value; confirm and pop on success, explain and stay on failure."""
        result = self._config.apply(self._key, event.value)
        if not result.ok:
            self.query_one("#detail", Static).update(f"✗ {result.message}")
            return
        self._setting().value = result.value
        below = self.menu_app.screen_stack[-2]
        if isinstance(below, ConfigPickerScreen):
            below.flash(f"✓ {result.message}")
        self.menu_app.pop_screen()

    def action_cancel(self) -> None:
        """Abandon the form without changing anything."""
        self.menu_app.pop_screen()


class NewJobScreen(Screen[None]):
    """Name a new job, then launch a fresh session on it — a text-entry *launcher*.

    Unlike the create form (a browser that stays in the TUI), a valid name exits the whole
    app with a ``start`` choice; the CLI wiring then launches the client, exactly like
    ``gmlw start <job>``. The name is validated in-form (via the injected ``validate_job``)
    so an unusable name never tears the menu down only to fail at the prompt. Esc cancels.
    """

    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "cancel", "Cancel")]

    @property
    def menu_app(self) -> MenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`MenuApp`."""
        return cast("MenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]

    def compose(self) -> ComposeResult:
        """A breadcrumb, the name input, a status line, and the key hints."""
        t = i18n.active().t
        yield Static(f"gmlw > {t('tui.job')} > {t('tui.job.new')}", id="crumb")
        yield Input(placeholder=t("tui.newjob.placeholder"), id="name")
        with Container(id="status"):
            yield Static(t("tui.newjob.hint"), id="detail")
            yield Static(t("tui.newjob.keys"), id="keys")

    def on_mount(self) -> None:
        """Focus the input so the user can just start typing."""
        self.query_one("#name", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Validate the typed name; launch on success, explain and stay on failure."""
        name = event.value.strip()
        error = (
            i18n.active().t("tui.newjob.empty") if not name else self.menu_app.validate_job(name)
        )
        if error is not None:
            self.query_one("#detail", Static).update(f"✗ {error}")
            return
        self.menu_app.exit(MenuChoice(action="start", job=name))

    def action_cancel(self) -> None:
        """Abandon the form and return to the Job menu."""
        self.menu_app.pop_screen()


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
        """Picking a job opens its session picker (choose which session to resume)."""
        if item.action == "pick":
            self.menu_app.push_screen(SessionPickerScreen(item.payload))


class SessionPickerScreen(_MenuScreen):
    """Pick which session of a job to resume: date · client · folder, latest marked.

    Rows for non-resumable clients (codex/vibe) are shown but disabled. A session whose
    client differs from the current default carries a "will launch on <client>" note, since
    a resume relaunches the session's client, not the default. Selecting one exits the app
    with a resume choice carrying the specific session id.
    """

    def __init__(self, job: str) -> None:
        """Bind the picker to the job whose sessions it lists."""
        super().__init__()
        self._job = job

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job > Resume > <job>."""
        t = i18n.active().t
        return f"gmlw > {t('tui.job')} > {t('tui.job.resume')} > {self._job}"

    def _sessions(self) -> list[SessionChoice]:
        return self.menu_app.sessions_for(self._job)

    def menu_items(self) -> list[_Item]:
        """One row per session (newest last); non-resumable rows are disabled.

        Three leading icons make the state glanceable: ``▶`` resume on your current client,
        ``↪`` resume but switch to the session's client, ``🔒`` cannot resume. On a switch the
        client is emphasised in-row (broken out of the dim subtitle) so it is seen without
        reading the footer; the detail panel still spells it out.
        """
        t = i18n.active().t
        current = self.menu_app.current_client
        items: list[_Item] = []
        for s in self._sessions():
            folder = s.cwd if s.cwd else t("tui.resume.no_folder")
            title = f"{s.session_id}  ·  {t('tui.resume.latest')}" if s.is_latest else s.session_id
            client = s.client
            if not s.resumable:
                icon, note = "🔒", t("tui.resume.cannot", client=s.client)
            elif s.client != current:
                icon, note = "↪", t("tui.resume.will_launch", client=s.client)
                client = f"↪ [b]{s.client}[/b]"  # in-row: mark + bold the client it switches to
            else:
                icon, note = "▶", ""
            items.append(
                _Item(
                    icon,
                    title,
                    f"{s.date} · {client} · {folder}",
                    "resume:pick",
                    payload=s.session_id,
                    note=note,
                    disabled=not s.resumable,
                )
            )
        return items

    def initial_index(self) -> int:
        """Open on the latest resumable session, else the first row."""
        sessions = self._sessions()
        for i in reversed(range(len(sessions))):
            if sessions[i].resumable:
                return i
        return 0

    def handle(self, item: _Item) -> None:
        """A picked session exits the app with a resume choice carrying its id."""
        if item.action == "resume:pick":
            self.menu_app.exit(MenuChoice(action="resume", job=self._job, session=item.payload))


class JobListScreen(_MenuScreen):
    """Browse the jobs with recorded activity; drill into one to see its sessions.

    A read-only *browser* (a sibling of :class:`JobPickerScreen` without the launch): selecting
    a job opens its :class:`SessionListScreen`. Reuses the injected ``jobs`` -- no new wiring.
    """

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job > List."""
        t = i18n.active().t
        return f"gmlw > {t('tui.job')} > {t('tui.job.list')}"

    def menu_items(self) -> list[_Item]:
        """One row per job, carrying the job id as payload (empty -> the base empty state)."""
        t = i18n.active().t
        return [
            _Item(
                "🗂", j.job, t("tui.sessions", count=j.session_count), "joblist:job", payload=j.job
            )
            for j in self.menu_app.jobs
        ]

    def handle(self, item: _Item) -> None:
        """Selecting a job opens its (read-only) session list."""
        if item.action == "joblist:job":
            self.menu_app.push_screen(SessionListScreen(item.payload))


class SessionListScreen(_MenuScreen):
    """Read-only view of a job's sessions: date · client · folder, latest marked, resumability.

    Unlike the resume picker, nothing is launched and nothing is disabled -- every session is
    shown for inspection, with a plain resumable/not-resumable note. The detail panel shows the
    highlighted row; Enter does nothing, Esc goes back.
    """

    def __init__(self, job: str) -> None:
        """Bind the view to the job whose sessions it lists."""
        super().__init__()
        self._job = job

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job > List > <job>."""
        t = i18n.active().t
        return f"gmlw > {t('tui.job')} > {t('tui.job.list')} > {self._job}"

    def menu_items(self) -> list[_Item]:
        """One row per session (newest last), each spelling out its metadata read-only."""
        t = i18n.active().t
        items: list[_Item] = []
        for s in self.menu_app.sessions_for(self._job):
            folder = s.cwd if s.cwd else t("tui.resume.no_folder")
            title = f"{s.session_id}  ·  {t('tui.resume.latest')}" if s.is_latest else s.session_id
            note = (
                t("tui.joblist.resumable")
                if s.resumable
                else t("tui.joblist.not_resumable", client=s.client)
            )
            items.append(
                _Item(
                    "📄",
                    title,
                    f"{s.date} · {s.client} · {folder}",
                    "joblist:session",
                    payload=s.session_id,
                    note=note,
                )
            )
        return items

    def handle(self, item: _Item) -> None:
        """Read-only: selecting a session does nothing (the detail panel is the whole view)."""


class JobExportScreen(_MenuScreen):
    """Pick a job to export; selecting one opens the destination chooser.

    A read-only sibling of :class:`JobListScreen` -- reuses the injected ``jobs``, then hands
    off to :class:`ExportDestScreen` for the chosen job.
    """

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job > Export."""
        t = i18n.active().t
        return f"gmlw > {t('tui.job')} > {t('tui.job.export')}"

    def menu_items(self) -> list[_Item]:
        """One row per job, carrying the job id as payload (empty -> the base empty state)."""
        t = i18n.active().t
        return [
            _Item(
                "📊", j.job, t("tui.sessions", count=j.session_count), "export:job", payload=j.job
            )
            for j in self.menu_app.jobs
        ]

    def handle(self, item: _Item) -> None:
        """Selecting a job opens the destination chooser (view here / save to file)."""
        if item.action == "export:job":
            self.menu_app.push_screen(ExportDestScreen(item.payload))


class ExportDestScreen(_MenuScreen):
    """Choose where a job's usage goes: a summary in the terminal, or the full report to a file.

    The report read is O(turns) and slow on big jobs, so this instant chooser comes *before* any
    read: pick a destination, then the chosen screen loads under a spinner.
    """

    def __init__(self, job: str) -> None:
        """Bind the chooser to the job being exported."""
        super().__init__()
        self._job = job

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job > Export > <job>."""
        t = i18n.active().t
        return f"gmlw > {t('tui.job')} > {t('tui.job.export')} > {self._job}"

    def menu_items(self) -> list[_Item]:
        """Two destinations: view a summary here, or save the full JSON report to a file."""
        t = i18n.active().t
        return [
            _Item("📈", t("export.dest.view"), t("export.dest.view.d"), "export:view"),
            _Item("💾", t("export.dest.file"), t("export.dest.file.d"), "export:file"),
        ]

    def handle(self, item: _Item) -> None:
        """Open the summary view, or the save-to-file screen."""
        if item.action == "export:view":
            self.menu_app.push_screen(UsageSummaryScreen(self._job))
        elif item.action == "export:file":
            self.menu_app.push_screen(SaveReportScreen(self._job))


class UsageSummaryScreen(Screen[None]):
    """A job's usage summary: totals, a by-model table, and a by-session-cost table.

    The slow ledger read runs in a background thread (so the UI never freezes), with a spinner
    over the report area until it lands. The tables are Textual ``DataTable``s -- virtualized, so
    they stay responsive no matter how many rows. The full per-turn detail is not shown here; it
    lives in the JSON file export.
    """

    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "back", "Back")]

    def __init__(self, job: str) -> None:
        """Bind the view to the job whose usage it summarises."""
        super().__init__()
        self._job = job

    @property
    def menu_app(self) -> MenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`MenuApp`."""
        return cast("MenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]

    def compose(self) -> ComposeResult:
        """A breadcrumb, the (initially loading) report area, and the key hints."""
        t = i18n.active().t
        yield Static(f"gmlw > {t('tui.job')} > {t('tui.job.export')} > {self._job}", id="crumb")
        with VerticalScroll(id="report"):
            yield Static("", id="summary")
            yield Static(t("export.by_model"), classes="section")
            yield DataTable(id="models", cursor_type="row", zebra_stripes=True)
            yield Static(t("export.by_session"), classes="section")
            yield DataTable(id="sessions", cursor_type="row", zebra_stripes=True)
        yield Static(t("tui.export.keys"), id="keys")

    def on_mount(self) -> None:
        """Show the spinner and kick the read onto a worker thread."""
        self.query_one("#report", VerticalScroll).loading = True
        self._load()

    @work(thread=True, exclusive=True)
    def _load(self) -> UsageView:
        """Read + aggregate the report off the event loop (returns; never touches widgets)."""
        return self.menu_app.usage_view(self._job)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Populate the tables when the read lands; show a failure line if it errored."""
        if event.state is WorkerState.SUCCESS:
            result = cast("UsageView", event.worker.result)  # pyright: ignore[reportUnknownMemberType]
            self._populate(result)
        elif event.state is WorkerState.ERROR:
            self.query_one("#summary", Static).update(i18n.active().t("export.failed"))
            self.query_one("#report", VerticalScroll).loading = False

    def _populate(self, view: UsageView) -> None:
        """Fill the summary line and the two tables from the loaded view."""
        t = i18n.active().t
        self.query_one("#summary", Static).update(view.summary)
        if not view.empty:
            models = cast("DataTable[str]", self.query_one("#models", DataTable))
            models.add_columns(
                t("export.col.model"),
                t("export.col.calls"),
                t("export.col.input"),
                t("export.col.output"),
                t("export.col.cache"),
                t("export.col.duration"),
            )
            models.add_rows(view.model_rows)
            sessions = cast("DataTable[str]", self.query_one("#sessions", DataTable))
            sessions.add_columns(t("export.col.session"), t("export.col.cost"))
            sessions.add_rows(view.session_rows)
        self.query_one("#report", VerticalScroll).loading = False

    def action_back(self) -> None:
        """Pop back to the destination chooser."""
        self.menu_app.pop_screen()


class SaveReportScreen(Screen[None]):
    """Write a job's full report to a JSON file, off the event loop, then show the path.

    The write (which first reads the whole report) runs in a worker thread under a spinner; on
    success the saved path is shown, on failure a plain error line. Esc goes back.
    """

    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "back", "Back")]

    def __init__(self, job: str) -> None:
        """Bind the screen to the job whose report it saves."""
        super().__init__()
        self._job = job

    @property
    def menu_app(self) -> MenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`MenuApp`."""
        return cast("MenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]

    def compose(self) -> ComposeResult:
        """A breadcrumb, the status line (spinner, then the saved path), and the key hints."""
        t = i18n.active().t
        yield Static(f"gmlw > {t('tui.job')} > {t('tui.job.export')} > {self._job}", id="crumb")
        with Container(id="report"):
            yield Static(t("export.saving"), id="status_line")
        yield Static(t("tui.export.keys"), id="keys")

    def on_mount(self) -> None:
        """Show the spinner and kick the save onto a worker thread."""
        self.query_one("#report", Container).loading = True
        self._save()

    @work(thread=True, exclusive=True)
    def _save(self) -> str:
        """Write the report off the event loop, returning the path (or ``""`` when unwired)."""
        return self.menu_app.save_usage(self._job)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Show the saved path on success, or a failure line on error."""
        status = self.query_one("#status_line", Static)
        if event.state is WorkerState.SUCCESS:
            path = cast("str", event.worker.result)  # pyright: ignore[reportUnknownMemberType]
            status.update(i18n.active().t("export.saved", path=path))
            self.query_one("#report", Container).loading = False
        elif event.state is WorkerState.ERROR:
            status.update(i18n.active().t("export.save_failed"))
            self.query_one("#report", Container).loading = False

    def action_back(self) -> None:
        """Pop back to the destination chooser."""
        self.menu_app.pop_screen()


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
    #report  { height: 1fr; padding: 0 1; }
    #summary { height: auto; padding: 1 0; }
    .section { text-style: bold; padding: 1 0 0 0; color: $text-muted; }
    #models, #sessions { height: auto; max-height: 20; margin: 0 0 1 0; }
    #status_line { padding: 1 1; }
    #status { dock: bottom; height: auto; }
    #detail { padding: 1 1; min-height: 2; height: auto; color: $text-muted; }
    #keys   { padding: 0 1; color: $text-muted; }
    ListItem { height: auto; padding: 0 1; background: transparent; }
    ListView > ListItem.-highlight { background: cyan 15%; }
    ListView:focus > ListItem.-highlight { background: cyan 25%; color: $text; }
    """
    TITLE = "gmlw"

    def __init__(  # noqa: PLR0913  (the app's injection seam: one kwarg per browser's data)
        self,
        jobs: list[JobChoice],
        *,
        switchers: dict[str, Switcher] | None = None,
        validate_job: Callable[[str], str | None] | None = None,
        sessions_for: Callable[[str], list[SessionChoice]] | None = None,
        usage_view: Callable[[str], UsageView] | None = None,
        save_usage: Callable[[str], str] | None = None,
        config: ConfigCatalog | None = None,
        current_client: str = "",
    ) -> None:
        """Bind the injected data the browsers read from and the callbacks they invoke.

        Args:
            jobs: The resumable jobs the Resume picker lists.
            switchers: The config switchers, keyed by ``persona`` / ``environment`` /
                ``role``. Each carries its options, current value, and a setter. A missing
                key just leaves that Config verb stubbed, so the app runs unwired in tests.
            validate_job: Validates a typed new-job name, returning an error message or
                ``None`` when it is acceptable; defaults to accepting anything (tests).
            sessions_for: Lists a job's sessions for the session picker (lazily, per job);
                defaults to none.
            usage_view: Builds a job's usage summary (totals + by-model + by-session rows) for
                the Export view (lazily, per job, on a worker thread); defaults to empty.
            save_usage: Writes a job's full report to a file and returns the path, for the
                save-to-file Export destination (lazily, per job); defaults to a no-op.
            config: The settings + setter the Config Get/Set browsers read and call; ``None``
                leaves those two Config verbs stubbed, so the app runs unwired in tests.
            current_client: The user's default client, to flag when a session's client
                differs (resuming will launch the session's client, not this one).
        """
        super().__init__()
        self.jobs = jobs
        self.switchers = switchers or {}
        self.validate_job = validate_job or _accept_any_job
        self.sessions_for = sessions_for or _no_sessions
        self.usage_view = usage_view or _no_usage_view
        self.save_usage = save_usage or _no_save
        self.config = config
        self.current_client = current_client

    def on_mount(self) -> None:
        """Open on the top (object) menu."""
        self.push_screen(TopMenuScreen())
