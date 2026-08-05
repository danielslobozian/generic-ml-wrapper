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

**Import timing matters here.** Textual reads ``BINDINGS`` as a class attribute, so a
footer label is resolved when this module is *imported*, not when a screen is shown. That
is fine because the module is imported lazily from the ``tui`` command, which runs after
the active localiser is installed -- so the labels come out in the user's language. Import
it any earlier and they would freeze in English. :func:`_key` marks every such label.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import ClassVar, cast

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.coordinate import Coordinate
from textual.screen import Screen
from textual.widgets import DataTable, Input, Label, ListItem, ListView, Static
from textual.worker import Worker, WorkerState

from generic_ml_wrapper.adapter.inbound.tui.banner import boxed_banner
from generic_ml_wrapper.application.domain.model.rule_axis import RuleAxis
from generic_ml_wrapper.application.domain.model.rule_group import RuleGroup
from generic_ml_wrapper.application.domain.model.workflow import Workflow
from generic_ml_wrapper.application.wiring import localization as i18n


def _key(key: str, action: str, label: str, **options: object) -> Binding:
    """A key binding whose footer label comes from the catalogue.

    Args:
        key: The key that triggers it.
        action: The action method name Textual dispatches to.
        label: The catalogue key for the label shown in the footer.
        options: Passed through to :class:`~textual.binding.Binding`.

    Returns:
        The binding, with its description already localised.
    """
    return Binding(key, action, i18n.active().t(label), **options)  # type: ignore[arg-type]


def _accept_any_job(_name: str) -> str | None:
    """Default new-job-name validator when the app runs unwired (tests): accept anything."""
    return None


def _accept_any_workflow(_name: str) -> str | None:
    """Default new-workflow-name validator when the app runs unwired (tests): accept anything."""
    return None


def _no_sessions(_job: str) -> list[SessionChoice]:
    """Default session lister when the app runs unwired (tests): no sessions."""
    return []


def _no_usage_view(job: str) -> UsageView:
    """Default usage view when the app runs unwired (tests): an empty report."""
    return UsageView(job=job, empty=True, summary="", model_rows=(), session_rows=())


def _no_clients() -> list[ClientChoice]:
    """Default when the app runs unwired: no client choice to offer, so none is asked for."""
    return []


def _no_rules() -> tuple[RuleGroup, ...]:
    """Default rule catalogue when the app runs unwired (tests): the user has none."""
    return ()


def _no_save(_job: str) -> str:
    """Default report saver when the app runs unwired (tests): no file written."""
    return ""


@dataclass(frozen=True)
class MenuChoice:
    """What the user asked the app to do, handed back to the wiring on exit.

    Job launchers use ``job`` (and, for ``"resume"``, the specific ``session``). Workflow
    launchers use ``workflow``: ``"run"`` runs it, ``"workflow_new"`` / ``"workflow_edit"``
    open an authoring session at the chosen ``guided`` depth (``workflow`` is ``None`` for a
    new workflow whose name is proposed at the end). ``"workflow_import"`` carries the
    ``archive`` to install from. ``client`` is the one this launch was pointed at, or
    ``None`` to use the configured default -- a per-launch choice, exactly like ``--client``
    on the CLI, and never a change to the default itself. A ``None`` return means "do
    nothing".

    Only things that need the terminal come back this way. Deleting does not -- it happens
    in the app, through an injected :class:`Deleter`, because leaving the menu to answer a
    question is a round trip that ends somewhere other than where it started.
    """

    action: str
    job: str | None = None
    session: str | None = None
    workflow: str | None = None
    guided: bool = False
    archive: str | None = None
    client: str | None = None


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
    marks the newest; ``usage`` is its already-rendered turn/cost cell (the word for
    "empty" when it never ran a turn), formatted by the wiring so the CLI listing and this
    app cannot describe the same session two different ways.
    """

    session_id: str
    client: str
    cwd: str | None
    resumable: bool
    date: str
    is_latest: bool
    usage: str = ""


@dataclass(frozen=True)
class Deleter:
    """The four calls the delete screens need, grouped as one injected collaborator.

    Grouped rather than four kwargs on the app, the way :class:`ConfigCatalog` groups the
    settings with their setter. The app stays free of ports: these are closures the wiring
    owns, and both halves matter -- ``preview_*`` is what the user is shown before deciding,
    and it must be measured by the same code that does the removing, or the question and the
    answer drift apart.

    Each ``preview_*`` returns the rendered footprint; each ``delete_*`` performs the removal
    and returns the line to show afterwards.
    """

    preview_jobs: Callable[[tuple[str, ...]], str]
    delete_jobs: Callable[[tuple[str, ...]], str]
    preview_sessions: Callable[[str, tuple[str, ...]], str]
    delete_sessions: Callable[[str, tuple[str, ...]], str]


@dataclass(frozen=True)
class ClientChoice:
    """One client a launch can be pointed at, as the picker shows it.

    Every row here is launchable -- the wiring only offers what is actually available, so
    unlike the resume picker there is nothing to disable. ``custom`` marks a client that
    came from the user's own ``[callers]`` config rather than the built-in catalog.
    """

    name: str
    display: str
    is_default: bool
    custom: bool = False


@dataclass(frozen=True)
class ImportAttempt:
    """What came back from trying to install an archive.

    ``needs_confirmation`` is the use case reporting a name clash rather than resolving it
    — the same answer the CLI turns into its replace prompt. Here it becomes a confirmation
    screen, and a yes re-runs the install with ``replace``.

    Attributes:
        message: The line to show — the outcome, the clash, or the error.
        needs_confirmation: Whether a workflow of that name already exists and the user
            has to say whether to displace it.
    """

    message: str
    needs_confirmation: bool = False


@dataclass(frozen=True)
class Archiver:
    """Sharing a workflow out and installing one in, as injected closures.

    Attributes:
        export: Packs a workflow by slug; returns the line to show.
        install: Installs an archive, optionally displacing a name clash.
        reload_workflows: Re-reads the catalogue after an install changed it.
    """

    export: Callable[[str], str]
    install: Callable[[str, bool], ImportAttempt]
    reload_workflows: Callable[[], list[Workflow]]


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
class ClientRow:
    """One supported client's row for the Config Clients table, pre-rendered by the wiring.

    All cells are display strings (``version`` reads "not installed" when absent, ``default``
    is a marker or empty) so the screen only fills the table. Two fields are not cells:
    ``name`` is the client *id* the screen writes when the row is made the default, and
    ``note`` is the caveat on the resumable cell (codex resumes only once its id is bound),
    shown in the detail line rather than crammed into the column.
    """

    client: str
    version: str
    resumable: str
    default: str
    name: str = ""
    note: str = ""


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
    ("🗑", "tui.job.delete", "job:delete", "gmlw jobs delete <job>"),
)
# Delete has two grains, exactly as the CLI does -- a whole job, or single sessions of one.
_DELETE_MENU = (
    ("🗑", "tui.del.jobs", "del:jobs", "gmlw jobs delete <job>"),
    ("🗑", "tui.del.sessions", "del:sessions", "gmlw sessions <job> delete <session>"),
)
_WORKFLOW_MENU = (
    ("⏵", "tui.wf.run", "wf:run", "gmlw run <workflow>"),
    ("✨", "tui.wf.create", "wf:create", "gmlw workflow new <name>"),
    ("✏️", "tui.wf.edit", "wf:edit", "gmlw workflow edit <name>"),
    ("📋", "tui.wf.list", "wf:list", "gmlw workflow list"),
    ("📦", "tui.wf.export", "wf:export", "gmlw workflow export <workflow>"),
    ("📥", "tui.wf.import", "wf:import", "gmlw workflow import <archive>"),
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
    ("🔌", "tui.cfg.clients", "cfg:clients", "gmlw clients"),
    ("🔁", "tui.cfg.setup", "cfg:setup", "gmlw init"),
)
_TOP_MENU = (
    ("🗂", "tui.job", "menu:job", ""),
    ("⚙", "tui.workflow", "menu:workflow", ""),
    ("🎛", "tui.config", "menu:config", ""),
    ("📏", "tui.rules", "menu:rules", ""),
    ("🚪", "tui.quit", "quit", ""),
)
# The icon per rule axis, so a group reads as a place or a craft at a glance.
_AXIS_ICON = {RuleAxis.ENVIRONMENT: "🌍", RuleAxis.ROLE: "🎓"}


def _wf_display(flow: Workflow) -> tuple[str, str]:
    """A workflow's row title and subtitle: its label, with the slug dimmed beneath.

    The slug is what ``gmlw run`` takes, so it stays on screen as the subtitle to identify
    the row. A workflow predating the sidecar has label == slug and no second line -- it
    reads exactly as its folder name always did.
    """
    if flow.label == flow.slug:
        return flow.slug, ""
    return flow.label, flow.slug


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
        _key("escape", "back", "tui.key.back"),
        _key("q", "quit_app", "tui.key.quit"),
    ]
    crumb: ClassVar[str] = "gmlw"
    show_banner: ClassVar[bool] = False
    # The i18n key shown when there are no rows; subclasses override for a tailored hint.
    empty_key: ClassVar[str] = "tui.empty"
    # The i18n key for the docked key-hints bar. A screen whose keys differ from the usual
    # move/select/back overrides it, so the bar describes the screen you are actually on.
    keys_key: ClassVar[str] = "tui.keys"
    # A one-shot detail message the next detail-sync shows instead of the cursor's row,
    # then clears -- so a confirmation survives a programmatic cursor move. Set it on a
    # screen you are about to push to have it greet the user on arrival.
    pending_message: str | None = None

    def tell(self, message: str) -> None:
        """Show ``message`` in the detail panel, now if mounted or on arrival if not."""
        if self.is_mounted:
            self.query_one("#detail", Static).update(message)
        else:
            self.pending_message = message

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
            yield Static(i18n.active().t(self.empty_key), id="empty")
        with Container(id="status"):
            yield Static("", id="detail")
            yield Static(i18n.active().t(self.keys_key), id="keys")

    def on_mount(self) -> None:
        """Prime the detail panel; a pending flash confirmation wins after the mount settles."""
        self._sync_detail()
        # Written after the initial-highlight sync, so the message survives it.
        if self.pending_message is not None:
            message, self.pending_message = self.pending_message, None
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


class ClientPickerScreen(_MenuScreen):
    """The last step before a launch: which client to run it on, this once.

    Takes the launch that is about to happen and returns the same launch with a client
    filled in. That is the whole screen -- it never inspects what kind of launch it is,
    so the job, run, and authoring flows all reach it the same way and none of them grew
    a branch for it.

    It opens on the configured default with the cursor already there, so ``⏎`` is
    "whatever I normally use" and choosing something else is a deliberate act. Nothing is
    written to config: this is ``--client`` for one launch, not a new default.
    """

    empty_key = "tui.client.none"

    def __init__(self, pending: MenuChoice) -> None:
        """Bind the picker to the launch it is completing."""
        super().__init__()
        self._pending = pending

    #: The launch action -> (object crumb key, verb crumb key). The picker is the last
    #: screen before something starts, so the breadcrumb has to still say what that is.
    _CRUMBS: ClassVar[dict[str, tuple[str, str]]] = {
        "start": ("tui.job", "tui.job.new"),
        "run": ("tui.workflow", "tui.wf.run"),
        "workflow_new": ("tui.workflow", "tui.wf.create"),
        "workflow_edit": ("tui.workflow", "tui.wf.edit"),
    }

    def header_text(self) -> str:
        """Breadcrumb: the launch being set up, what it targets, then Client."""
        t = i18n.active().t
        obj, verb = self._CRUMBS.get(self._pending.action, ("tui.client.crumb", ""))
        parts = ["gmlw", t(obj)]
        if verb:
            parts.append(t(verb))
        target = self._pending.job or self._pending.workflow
        if target:
            parts.append(target)
        parts.append(t("tui.client.crumb"))
        return " > ".join(parts)

    def _choices(self) -> list[ClientChoice]:
        return self.menu_app.launch_clients()

    def menu_items(self) -> list[_Item]:
        """One row per launchable client, the default marked and your own callers flagged."""
        t = i18n.active().t
        items: list[_Item] = []
        for choice in self._choices():
            if choice.is_default:
                icon = "●"
            elif choice.custom:
                icon = "🔌"
            else:
                icon = "○"
            items.append(
                _Item(
                    icon,
                    choice.display,
                    t("tui.client.default") if choice.is_default else t("tui.client.once"),
                    "client:pick",
                    payload=choice.name,
                    note=t("tui.client.custom") if choice.custom else "",
                )
            )
        return items

    def initial_index(self) -> int:
        """Open on the configured default, so ``⏎`` is the answer most people want.

        A default that is not among the offered clients (uninstalled, or removed from
        ``[callers]``) simply has no row, and the cursor starts at the top instead.
        """
        return next((i for i, c in enumerate(self._choices()) if c.is_default), 0)

    def handle(self, item: _Item) -> None:
        """Exit with the pending launch, now carrying the chosen client."""
        if item.action == "client:pick":
            self.menu_app.exit(replace(self._pending, client=item.payload))


class ConfirmScreen(Screen[bool]):
    """A yes/no question with the consequences spelled out above it.

    Opens on **No**. A destructive question whose default answer is the destructive one is
    a trap: the reflex on a new screen is ``⏎``, and here that reflex has to be the safe
    answer. Esc is the same as No.

    Dismisses with the answer, so the caller decides what happens next -- this screen knows
    nothing about what it is asking about.
    """

    BINDINGS: ClassVar[list[Binding]] = [
        _key("escape", "refuse", "tui.key.cancel"),
        _key("q", "refuse", "tui.key.cancel"),
    ]

    def __init__(  # noqa: PLR0913  (the question is its wording; each part is one argument)
        self,
        crumb: str,
        consequences: str,
        *,
        yes_key: str = "tui.confirm.delete",
        no_key: str = "tui.confirm.keep",
        warning_key: str = "tui.confirm.warning.delete",
        yes_icon: str = "🗑",
    ) -> None:
        """Bind the question to its breadcrumb, its consequences, and its own wording.

        The wording is per-question rather than fixed. A screen that says "Yes, delete —
        this cannot be undone" to someone importing a workflow is describing a different
        action from the one about to happen, and an import keeps a backup precisely so it
        *can* be undone.

        Args:
            crumb: The breadcrumb of the screen that asked, so the header does not move.
            consequences: The rendered preview of what confirming would do.
            yes_key: Catalogue key for the confirming answer (``.d`` is its subtitle).
            no_key: Catalogue key for the declining answer (``.d`` is its subtitle).
            warning_key: Catalogue key for the caveat under the answers.
            yes_icon: The icon on the confirming row.
        """
        super().__init__()
        self._crumb = crumb
        self._consequences = consequences
        self._yes_key = yes_key
        self._no_key = no_key
        self._warning_key = warning_key
        self._yes_icon = yes_icon

    def compose(self) -> ComposeResult:
        """Breadcrumb, the consequences, the two answers, then the docked hints."""
        t = i18n.active().t
        yield Static(self._crumb, id="crumb")
        yield Static(self._consequences, id="consequences")
        yield ListView(
            _Row(_Item("↩", t(self._no_key), t(f"{self._no_key}.d"), "no")),
            _Row(_Item(self._yes_icon, t(self._yes_key), t(f"{self._yes_key}.d"), "yes")),
            id="menu",
            initial_index=0,  # the safe answer is the one ⏎ lands on
        )
        with Container(id="status"):
            yield Static(t(self._warning_key), id="detail")
            yield Static(t("tui.keys.confirm"), id="keys")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Answer with the chosen row."""
        event.stop()
        if isinstance(event.item, _Row):
            self.dismiss(event.item.item.action == "yes")

    def action_refuse(self) -> None:
        """Esc (or q) is No — backing out of a question is never a yes."""
        self.dismiss(False)


class _MultiSelectScreen(_MenuScreen):
    """A menu screen where ``space`` ticks rows and ``⏎`` acts on everything ticked.

    The reason the delete screens exist at all: the issue behind them says that cleaning
    up one item at a time is not worth doing, which is how the list got long. So the
    selection is the unit here, not the row.

    ``⏎`` on an empty selection deliberately does nothing but say which key ticks a row.
    Treating the highlighted row as an implicit selection would turn the most reflexive
    keypress in the app into a delete nobody asked for.
    """

    BINDINGS: ClassVar[list[Binding]] = [
        *_MenuScreen.BINDINGS,
        _key("space", "toggle_row", "tui.key.toggle"),
    ]
    keys_key = "tui.keys.multi"
    ticked: ClassVar[str] = "☑"
    unticked: ClassVar[str] = "☐"

    def __init__(self) -> None:
        """Start with nothing ticked."""
        super().__init__()
        self._selected: set[str] = set()

    def preview(self, selected: tuple[str, ...]) -> str:
        """Render what acting on ``selected`` would do, for the confirmation screen."""
        raise NotImplementedError

    def perform(self, selected: tuple[str, ...]) -> str:
        """Act on ``selected`` and return the line to show afterwards."""
        raise NotImplementedError

    def reopened(self) -> _MultiSelectScreen:
        """A fresh instance of this screen, for re-reading the list after a change."""
        raise NotImplementedError

    def action_toggle_row(self) -> None:
        """Tick or untick the highlighted row, repainting its box in place."""
        row = self.query_one("#menu", ListView).highlighted_child
        if not isinstance(row, _Row):
            return
        payload = row.item.payload
        if payload in self._selected:
            self._selected.discard(payload)
            row.set_icon(self.unticked)
        else:
            self._selected.add(payload)
            row.set_icon(self.ticked)
        self._sync_detail()

    def handle(self, item: _Item) -> None:  # noqa: ARG002  (⏎ acts on the ticks, not the row)
        """``⏎``: ask about the ticked rows, or explain how to tick one when none are."""
        if not self._selected:
            self.query_one("#detail", Static).update(i18n.active().t("tui.del.none_selected"))
            self.menu_app.bell()
            return
        selected = tuple(i.payload for i in self.menu_items() if i.payload in self._selected)
        self.menu_app.push_screen(
            ConfirmScreen(self.header_text(), self.preview(selected)),
            lambda answered: self._answered(selected, answered),
        )

    def _answered(self, selected: tuple[str, ...], confirmed: bool | None) -> None:
        """Carry out the action if it was confirmed, then land back on a current list.

        Declining says nothing and shows nothing: the user already knows what they chose,
        and an acknowledgement they have to dismiss is one keypress of pure friction.
        """
        if not confirmed:
            return
        message = self.perform(selected)
        # The list this screen was built from is now out of date. Rather than patch rows,
        # swap in a freshly-read copy of the *same* screen -- so the user stays exactly
        # where they were, one level deep in the thing they are cleaning up, and sees the
        # outcome in the panel. Nothing left to clean means nothing left to stand on, so
        # that case steps back out instead.
        fresh = self.reopened()
        self.menu_app.pop_screen()
        if fresh.menu_items():
            fresh.pending_message = message
            self.menu_app.push_screen(fresh)
        else:
            self.menu_app.tell_current(message)

    def _sync_detail(self) -> None:
        """Show the highlighted row's description with the running tick count under it."""
        item = self._highlighted()
        loc = i18n.active()
        lines = [] if item is None else [item.subtitle]
        lines.append(
            loc.t("tui.del.selected", count=len(self._selected))
            if self._selected
            else loc.t("tui.del.none_selected")
        )
        self.query_one("#detail", Static).update("\n".join(lines))


class TopMenuScreen(_MenuScreen):
    """The front door: Job · Workflow · Config · Rules · Quit, under the banner."""

    show_banner = True

    def menu_items(self) -> list[_Item]:
        """The object rows: Job, Workflow, Config, Rules, Quit."""
        return _menu(_TOP_MENU)

    def handle(self, item: _Item) -> None:
        """Quit, or open the Job/Workflow/Config/Rules sub-menu."""
        if item.action == "quit":
            self.menu_app.exit(None)
        elif item.action == "menu:job":
            self.menu_app.push_screen(JobMenuScreen())
        elif item.action == "menu:workflow":
            self.menu_app.push_screen(WorkflowMenuScreen())
        elif item.action == "menu:config":
            self.menu_app.push_screen(ConfigMenuScreen())
        elif item.action == "menu:rules":
            self.menu_app.push_screen(RulesMenuScreen())

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
            self.menu_app.push_screen(NewSessionScreen())
        elif item.action == "job:list":
            self.menu_app.push_screen(JobListScreen())
        elif item.action == "job:export":
            self.menu_app.push_screen(JobExportScreen())
        elif item.action == "job:delete":
            self.menu_app.push_screen(DeleteMenuScreen())
        else:
            self._stub(item)


class WorkflowMenuScreen(_MenuScreen):
    """The Workflow object's verbs: Run and List are wired; Create/Edit are stubbed for now."""

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Workflow (localised)."""
        return f"gmlw > {i18n.active().t('tui.workflow')}"

    def menu_items(self) -> list[_Item]:
        """The Workflow verbs."""
        return _menu(_WORKFLOW_MENU)

    def handle(self, item: _Item) -> None:
        """Each Workflow verb: Run/Edit pick a workflow, Create names one, List browses."""
        if item.action == "wf:run":
            self.menu_app.push_screen(WorkflowPickerScreen("run"))
        elif item.action == "wf:edit":
            self.menu_app.push_screen(WorkflowPickerScreen("edit"))
        elif item.action == "wf:create":
            self.menu_app.push_screen(NewWorkflowScreen())
        elif item.action == "wf:list":
            self.menu_app.push_screen(WorkflowListScreen())
        elif item.action == "wf:export":
            self.menu_app.push_screen(WorkflowPickerScreen("export"))
        elif item.action == "wf:import":
            self.menu_app.push_screen(ImportWorkflowScreen())
        else:
            self._stub(item)


class WorkflowListScreen(_MenuScreen):
    """Read-only list of the runnable workflows (reuses the injected ``workflows``)."""

    empty_key = "tui.wf.none"

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Workflow > List."""
        t = i18n.active().t
        return f"gmlw > {t('tui.workflow')} > {t('tui.wf.list')}"

    def menu_items(self) -> list[_Item]:
        """One row per workflow; the detail panel shows how to run it."""
        return [
            _Item("📄", *_wf_display(flow), "wf:listrow", example=f"gmlw run {flow.slug}")
            for flow in self.menu_app.workflows
        ]

    def handle(self, item: _Item) -> None:
        """Read-only: selecting a workflow does nothing (the detail panel is the view)."""


class WorkflowPickerScreen(_MenuScreen):
    """Pick a workflow, to run it (``run``) or to edit it (``edit``).

    ``run`` exits the app with a run choice the wiring launches; ``edit`` moves on to the
    authoring-depth chooser first. An empty list points the user at Create.
    """

    empty_key = "tui.wf.none"

    def __init__(self, mode: str) -> None:
        """Bind the picker to its mode (``"run"`` or ``"edit"``)."""
        super().__init__()
        self._mode = mode

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Workflow > Run|Edit|Export."""
        t = i18n.active().t
        verb = t(f"tui.wf.{self._mode}")
        return f"gmlw > {t('tui.workflow')} > {verb}"

    def menu_items(self) -> list[_Item]:
        """One row per workflow: its label to read, its slug carried as the payload."""
        return [
            _Item("⏵", *_wf_display(flow), "wf:pick", payload=flow.slug)
            for flow in self.menu_app.workflows
        ]

    def handle(self, item: _Item) -> None:
        """Run exits with the choice; Export packs in place; Edit picks a depth first."""
        if item.action != "wf:pick":
            return
        if self._mode == "run":
            self.menu_app.launch(MenuChoice(action="run", workflow=item.payload))
        elif self._mode == "export":
            # Done here rather than on the way out: packing a zip asks nothing and changes
            # nothing you are looking at, so leaving the menu for it would cost the user
            # their place for no reason -- and exporting a second workflow is one keypress
            # away when the list is still in front of them.
            archiver = self.menu_app.archiver
            if archiver is not None:
                self.tell(archiver.export(item.payload))
        else:  # edit — choose the authoring depth, then launch the edit session
            self.menu_app.push_screen(GuidedChoiceScreen("workflow_edit", item.payload))


class NewWorkflowScreen(Screen[None]):
    """Name a new workflow (optional), then choose the authoring depth — a text-entry launcher.

    Unlike :class:`NewJobScreen`, an empty name is accepted: the authoring session proposes one
    at the end. A non-empty name is validated in-form (via the injected ``validate_workflow``)
    so a bad seed name never tears the menu down only to fail at the prompt. Esc cancels.
    """

    BINDINGS: ClassVar[list[Binding]] = [_key("escape", "cancel", "tui.key.cancel")]

    @property
    def menu_app(self) -> MenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`MenuApp`."""
        return cast("MenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]

    def compose(self) -> ComposeResult:
        """A breadcrumb, the (optional) name input, a status line, and the key hints."""
        t = i18n.active().t
        yield Static(f"gmlw > {t('tui.workflow')} > {t('tui.wf.create')}", id="crumb")
        yield Input(placeholder=t("tui.wf.new.placeholder"), id="name")
        with Container(id="status"):
            yield Static(t("tui.wf.new.hint"), id="detail")
            yield Static(t("tui.wf.new.keys"), id="keys")

    def on_mount(self) -> None:
        """Focus the input so the user can just start typing (or press Enter to skip naming)."""
        self.query_one("#name", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Validate the (optional) name, then move to the authoring-depth chooser."""
        name = event.value.strip()
        error = self.menu_app.validate_workflow(name)
        if error is not None:  # a non-empty but unusable name — keep the form so it can be fixed
            self.query_one("#detail", Static).update(f"✗ {error}")
            return
        self.menu_app.push_screen(GuidedChoiceScreen("workflow_new", name or None))

    def action_cancel(self) -> None:
        """Abandon the form and return to the Workflow menu."""
        self.menu_app.pop_screen()


class ImportWorkflowScreen(Screen[None]):
    """Type or paste the path of an archive to import — a text-entry launcher.

    A path rather than a picker because the archive a user wants is usually the one a
    colleague just sent them, sitting wherever their browser put it, not in gmlw's own
    exports folder. The path is checked here so a typo is fixed in the form rather than
    tearing the menu down to fail at the prompt.

    The install happens here. A name clash is the one question it can raise, and the use
    case reports that back rather than resolving it -- so it becomes a confirmation screen
    and a yes re-runs the install with ``replace``, without the menu going anywhere.
    """

    BINDINGS: ClassVar[list[Binding]] = [_key("escape", "cancel", "tui.key.cancel")]

    @property
    def menu_app(self) -> MenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`MenuApp`."""
        return cast("MenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]

    def compose(self) -> ComposeResult:
        """A breadcrumb, the archive-path input, a status line, and the key hints."""
        t = i18n.active().t
        yield Static(f"gmlw > {t('tui.workflow')} > {t('tui.wf.import')}", id="crumb")
        yield Input(placeholder=t("tui.wf.import.placeholder"), id="archive")
        with Container(id="status"):
            yield Static(t("tui.wf.import.hint"), id="detail")
            yield Static(t("tui.wf.new.keys"), id="keys")

    def on_mount(self) -> None:
        """Focus the input so the user can paste straight away."""
        self.query_one("#archive", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Hand the typed path to the import, and show whatever comes back.

        Whether there is a file there, and what ``~`` means, are not this screen's
        questions -- the import answers both, and refuses with a message of its own. Asking
        first only made two places responsible for the same answer.
        """
        raw = event.value.strip()
        if not raw:
            return
        self._install(raw, replace=False)

    def _install(self, archive: str, *, replace: bool) -> None:
        """Install the archive, asking about a name clash if the use case reports one."""
        archiver = self.menu_app.archiver
        if archiver is None:
            return
        attempt = archiver.install(archive, replace)
        if attempt.needs_confirmation:
            self.menu_app.push_screen(
                ConfirmScreen(
                    f"gmlw > {i18n.active().t('tui.workflow')} > "
                    f"{i18n.active().t('tui.wf.import')}",
                    attempt.message,
                    yes_key="tui.confirm.replace",
                    no_key="tui.confirm.keep_existing",
                    warning_key="tui.confirm.warning.replace",
                    yes_icon="📥",
                ),
                lambda confirmed: self._install(archive, replace=True) if confirmed else None,
            )
            return
        self._finish(attempt.message)

    def _finish(self, message: str) -> None:
        """Report where the import landed, back on the Workflow menu.

        The path has been consumed, so the form has nothing left to do -- but a failure
        keeps it, and its message, so a mistyped path can be corrected in place.
        """
        if message.startswith("✗"):
            self.query_one("#detail", Static).update(message)
            return
        self.menu_app.refresh_workflows()  # a new (or replaced) workflow is now runnable
        self.menu_app.pop_screen()
        self.menu_app.tell_current(message)

    def action_cancel(self) -> None:
        """Abandon the form and return to the Workflow menu."""
        self.menu_app.pop_screen()


class GuidedChoiceScreen(_MenuScreen):
    """Choose the authoring depth (guided vs quick), then exit to launch the session.

    Bound to the authoring action (``workflow_new`` / ``workflow_edit``) and the workflow name
    (``None`` for a new, unnamed workflow). Picking a depth exits the app with the choice; the
    wiring then launches the authoring session at that depth, exactly like ``--guided`` /
    ``--quick`` on the CLI.
    """

    def __init__(self, action: str, workflow: str | None) -> None:
        """Bind the chooser to the authoring action and the workflow it applies to."""
        super().__init__()
        self._action = action
        self._workflow = workflow

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Workflow > Create|Edit."""
        t = i18n.active().t
        verb = t("tui.wf.create") if self._action == "workflow_new" else t("tui.wf.edit")
        return f"gmlw > {t('tui.workflow')} > {verb}"

    def menu_items(self) -> list[_Item]:
        """Two rows: the guided (facilitative) experience or the quick (lean) interview."""
        t = i18n.active().t
        return [
            _Item("✨", t("tui.wf.guided"), t("tui.wf.guided.d"), "guided:yes"),
            _Item("⏩", t("tui.wf.quick"), t("tui.wf.quick.d"), "guided:no"),
        ]

    def handle(self, item: _Item) -> None:
        """Move on to the client step with the authoring choice at the picked depth."""
        if item.action in ("guided:yes", "guided:no"):
            self.menu_app.launch(
                MenuChoice(
                    action=self._action,
                    workflow=self._workflow,
                    guided=item.action == "guided:yes",
                )
            )


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
        elif item.action == "cfg:list" and self.menu_app.config is not None:
            self.menu_app.push_screen(ConfigListScreen())
        elif item.action == "cfg:clients" and self.menu_app.clients is not None:
            self.menu_app.push_screen(ClientsScreen())
        elif item.action == "cfg:setup":  # a launcher: exit, the wiring re-runs init after teardown
            self.menu_app.exit(MenuChoice(action="init"))
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
        reopened.pending_message = i18n.active().t("tui.create.done", label=choice.label)
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

    BINDINGS: ClassVar[list[Binding]] = [_key("escape", "cancel", "tui.key.cancel")]

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
        _key("escape", "back", "tui.key.back"),
        _key("up", "cursor(-1)", "tui.key.up", show=False, priority=True),
        _key("down", "cursor(1)", "tui.key.down", show=False, priority=True),
        _key("enter", "pick", "tui.key.select", show=False, priority=True),
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

    async def on_input_changed(self, event: Input.Changed) -> None:
        """Refilter the list as the user types."""
        self._filter = event.value
        await self._rebuild()

    async def on_screen_resume(self) -> None:
        """Returning from a value editor: rebuild (a set may have changed a value), then flash."""
        await self._rebuild()
        if self.pending_message is not None:  # a confirmation queued by the editor before it popped
            message, self.pending_message = self.pending_message, None
            self.call_after_refresh(lambda: self.query_one("#detail", Static).update(message))

    async def _rebuild(self) -> None:
        """Rebuild the list rows from the current filter and settings, highlighting the first.

        The clear is *awaited*: ``ListView.clear`` removes its rows asynchronously, so setting
        the highlight straight after would land it on a row already on its way out -- leaving
        the rebuilt list with nothing marked, and making the first Down look like it skipped a
        row. Awaiting means the index is set on the rows the user is actually looking at.
        """
        menu = self.query_one("#menu", ListView)
        await menu.clear()  # also resets the index to None, so setting it below re-highlights
        items = self.menu_items()
        for item in items:
            menu.append(_Row(item))
        menu.index = 0 if items else None

    def flash(self, message: str) -> None:
        """Queue a one-shot confirmation to show when this picker is next resumed."""
        self.pending_message = message

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

    BINDINGS: ClassVar[list[Binding]] = [_key("escape", "cancel", "tui.key.cancel")]

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


class NewSessionScreen(_MenuScreen):
    """Which job the fresh session belongs to: one you already have, or a new name.

    ``Job > New`` used to be the text field alone, which made starting more work on a job
    you already had a memory test -- the app was showing that list in two other places
    while asking you to retype a name out of it.

    A new name stays one keypress away, and stays *first*: it is what the verb says, it is
    the only row on an install with no jobs yet, and a fixed first row means the flow does
    not shift under you as jobs come and go.

    Picking an existing job goes straight on to the client step. That is a *new session*
    on that job, numbered after its last -- the same thing ``gmlw start <existing-job>``
    has always done, which is why nothing new had to be built underneath this.
    """

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job > New."""
        t = i18n.active().t
        return f"gmlw > {t('tui.job')} > {t('tui.job.new')}"

    def menu_items(self) -> list[_Item]:
        """The type-a-name row, then one row per job already recorded."""
        t = i18n.active().t
        rows = [
            _Item(
                "✏️",
                t("tui.newsession.type"),
                t("tui.newsession.type.d"),
                "session:type",
                "gmlw start <job>",
            )
        ]
        rows += [
            _Item(
                "🗂",
                job.job,
                t("tui.sessions", count=job.session_count),
                "session:job",
                f"gmlw start {job.job}",
                payload=job.job,
            )
            for job in self.menu_app.jobs
        ]
        return rows

    def handle(self, item: _Item) -> None:
        """Typing opens the name form; an existing job goes on to the client step."""
        if item.action == "session:type":
            self.menu_app.push_screen(NewJobScreen())
        elif item.action == "session:job":
            self.menu_app.launch(MenuChoice(action="start", job=item.payload))


class NewJobScreen(Screen[None]):
    """Name a new job, then launch a fresh session on it — a text-entry *launcher*.

    Unlike the create form (a browser that stays in the TUI), a valid name exits the whole
    app with a ``start`` choice; the CLI wiring then launches the client, exactly like
    ``gmlw start <job>``. The name is validated in-form (via the injected ``validate_job``)
    so an unusable name never tears the menu down only to fail at the prompt. Esc cancels.
    """

    BINDINGS: ClassVar[list[Binding]] = [_key("escape", "cancel", "tui.key.cancel")]

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
        self.menu_app.launch(MenuChoice(action="start", job=name))

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


class SessionListScreen(Screen[None]):
    """Read-only table of a job's sessions: session · date · client · folder · resumable.

    Unlike the resume picker, nothing is launched and nothing is disabled -- every session is
    shown for inspection in a DataTable. The rows are already in memory (via ``sessions_for``),
    so it fills synchronously (no worker). Read-only; Esc goes back.
    """

    BINDINGS: ClassVar[list[Binding]] = [_key("escape", "back", "tui.key.back")]

    def __init__(self, job: str) -> None:
        """Bind the view to the job whose sessions it lists."""
        super().__init__()
        self._job = job

    @property
    def menu_app(self) -> MenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`MenuApp`."""
        return cast("MenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]

    def compose(self) -> ComposeResult:
        """A breadcrumb, the sessions table, and the key hints."""
        t = i18n.active().t
        yield Static(f"gmlw > {t('tui.job')} > {t('tui.job.list')} > {self._job}", id="crumb")
        with Container(id="report"):
            yield DataTable(id="session_table", cursor_type="row", zebra_stripes=True)
        yield Static(t("tui.export.keys"), id="keys")

    def on_mount(self) -> None:
        """Fill the sessions table (newest last), latest marked, resumable as yes/no."""
        t = i18n.active().t
        table = cast("DataTable[str]", self.query_one("#session_table", DataTable))
        table.add_columns(
            t("tui.joblist.col.session"),
            t("tui.joblist.col.date"),
            t("tui.joblist.col.client"),
            t("tui.joblist.col.folder"),
            t("tui.joblist.col.resumable"),
        )
        for s in self.menu_app.sessions_for(self._job):
            session = f"{s.session_id} · {t('tui.resume.latest')}" if s.is_latest else s.session_id
            folder = s.cwd if s.cwd else t("tui.resume.no_folder")
            resumable = t("clients.yes") if s.resumable else t("clients.no")
            table.add_row(session, s.date, s.client, folder, resumable)

    def action_back(self) -> None:
        """Pop back to the job picker."""
        self.menu_app.pop_screen()


class DeleteMenuScreen(_MenuScreen):
    """Job > Delete: pick the grain — whole jobs, or single sessions of one job."""

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job > Delete."""
        t = i18n.active().t
        return f"gmlw > {t('tui.job')} > {t('tui.job.delete')}"

    def menu_items(self) -> list[_Item]:
        """The two delete grains."""
        return _menu(_DELETE_MENU)

    def handle(self, item: _Item) -> None:
        """Jobs ticks jobs directly; Sessions picks a job first, then ticks its sessions."""
        if item.action == "del:jobs":
            self.menu_app.push_screen(JobDeleteScreen())
        elif item.action == "del:sessions":
            self.menu_app.push_screen(DeleteJobPickerScreen())


class JobDeleteScreen(_MultiSelectScreen):
    """Tick whole jobs to remove; ``⏎`` asks, and confirming removes them here.

    The whole flow stays in the app. The removal itself is the injected
    :class:`Deleter`'s, so this screen still holds no port -- it asks a question, calls a
    closure, and shows what came back.
    """

    empty_key = "tui.del.empty"

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job > Delete > Jobs."""
        t = i18n.active().t
        return f"gmlw > {t('tui.job')} > {t('tui.job.delete')} > {t('tui.del.jobs')}"

    def menu_items(self) -> list[_Item]:
        """One tickable row per job, carrying the job id as payload."""
        t = i18n.active().t
        return [
            _Item(
                self.ticked if j.job in self._selected else self.unticked,
                j.job,
                t("tui.sessions", count=j.session_count),
                "del:job",
                payload=j.job,
            )
            for j in self.menu_app.jobs
        ]

    def preview(self, selected: tuple[str, ...]) -> str:
        """What removing the ticked jobs would take with it."""
        deleter = self.menu_app.deleter
        return "" if deleter is None else deleter.preview_jobs(selected)

    def perform(self, selected: tuple[str, ...]) -> str:
        """Remove the ticked jobs, then re-read the list they came from."""
        deleter = self.menu_app.deleter
        if deleter is None:
            return ""
        message = deleter.delete_jobs(selected)
        self.menu_app.refresh_jobs()
        return message

    def reopened(self) -> _MultiSelectScreen:
        """A fresh job list, without the ones just removed."""
        return JobDeleteScreen()


class DeleteJobPickerScreen(_MenuScreen):
    """Pick which job to delete sessions from, before ticking the sessions themselves."""

    empty_key = "tui.del.empty"

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job > Delete > Sessions."""
        t = i18n.active().t
        return f"gmlw > {t('tui.job')} > {t('tui.job.delete')} > {t('tui.del.sessions')}"

    def menu_items(self) -> list[_Item]:
        """One row per job, carrying the job id as payload."""
        t = i18n.active().t
        return [
            _Item("🗂", j.job, t("tui.sessions", count=j.session_count), "del:pick", payload=j.job)
            for j in self.menu_app.jobs
        ]

    def handle(self, item: _Item) -> None:
        """Selecting a job opens its session-delete list."""
        if item.action == "del:pick":
            self.menu_app.push_screen(SessionDeleteScreen(item.payload))


class SessionDeleteScreen(_MultiSelectScreen):
    """Tick sessions of one job to remove; ``⏎`` hands the selection back to the wiring.

    Every session is tickable, resumable or not: this is not the resume picker, and a
    session nobody can reopen is if anything the likelier one to be cleaning up.
    """

    empty_key = "tui.del.empty.sessions"

    def __init__(self, job: str) -> None:
        """Bind the screen to the job whose sessions it lists."""
        super().__init__()
        self._job = job

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Job > Delete > Sessions > <job>."""
        t = i18n.active().t
        return (
            f"gmlw > {t('tui.job')} > {t('tui.job.delete')} > {t('tui.del.sessions')} > {self._job}"
        )

    def menu_items(self) -> list[_Item]:
        """One tickable row per session: date, client, and what it actually used."""
        t = i18n.active().t
        return [
            _Item(
                self.ticked if s.session_id in self._selected else self.unticked,
                s.session_id,
                t("tui.del.session.row", date=s.date, client=s.client, usage=s.usage),
                "del:session",
                payload=s.session_id,
            )
            for s in self.menu_app.sessions_for(self._job)
        ]

    def preview(self, selected: tuple[str, ...]) -> str:
        """What removing the ticked sessions would take with it."""
        deleter = self.menu_app.deleter
        return "" if deleter is None else deleter.preview_sessions(self._job, selected)

    def perform(self, selected: tuple[str, ...]) -> str:
        """Remove the ticked sessions. The job's own list re-reads through ``sessions_for``."""
        deleter = self.menu_app.deleter
        if deleter is None:
            return ""
        message = deleter.delete_sessions(self._job, selected)
        self.menu_app.refresh_jobs()  # the job's session count changed in the lists above
        return message

    def reopened(self) -> _MultiSelectScreen:
        """The same job's sessions, re-read without the ones just removed."""
        return SessionDeleteScreen(self._job)


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

    BINDINGS: ClassVar[list[Binding]] = [_key("escape", "back", "tui.key.back")]

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

    BINDINGS: ClassVar[list[Binding]] = [_key("escape", "back", "tui.key.back")]

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


class ClientsScreen(Screen[None]):
    """The supported clients + versions, loaded on a worker into a DataTable.

    Reads each installed version (a subprocess that can hang), so it loads on a background
    thread with a spinner, like the Export summary. Esc goes back.

    The one thing this view can *change* is which client is the default: the table already
    answers "what have I got?", so answering "use that one" here saves a trip through
    Config > Set to type a key. Selecting a row writes ``client.default`` through the injected
    setter and moves the marker in place. Without that setter (unwired, in tests) it stays
    read-only. A client that is not installed can still be picked, exactly as
    ``gmlw config set client.default`` allows -- the launch preflight is what guides you.
    """

    BINDINGS: ClassVar[list[Binding]] = [_key("escape", "back", "tui.key.back")]
    # The Default column, whose marker moves as the user switches (client · version ·
    # resumable · default).
    _DEFAULT_COLUMN = 3

    def __init__(self) -> None:
        """Start with no rows; the worker fills them (and the setter reads them back)."""
        super().__init__()
        self._rows: list[ClientRow] = []

    @property
    def menu_app(self) -> MenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`MenuApp`."""
        return cast("MenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]

    def compose(self) -> ComposeResult:
        """A breadcrumb, the (initially loading) clients table, then detail + key hints."""
        t = i18n.active().t
        yield Static(f"gmlw > {t('tui.config')} > {t('tui.cfg.clients')}", id="crumb")
        with Container(id="report"):
            yield DataTable(id="clients", cursor_type="row", zebra_stripes=True)
        with Container(id="status"):
            yield Static("", id="detail")
            keys = "tui.clients.keys" if self.menu_app.set_default_client else "tui.export.keys"
            yield Static(t(keys), id="keys")

    def on_mount(self) -> None:
        """Show the spinner and kick the version reads onto a worker thread."""
        self.query_one("#report", Container).loading = True
        self._load()

    @work(thread=True, exclusive=True)
    def _load(self) -> list[ClientRow]:
        """Read the clients + versions off the event loop (pushed only when wired)."""
        clients = self.menu_app.clients
        return clients() if clients is not None else []

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Fill the table when the reads land; drop the spinner on error."""
        if event.state is WorkerState.SUCCESS:
            self._populate(cast("list[ClientRow]", event.worker.result))  # pyright: ignore[reportUnknownMemberType]
        elif event.state is WorkerState.ERROR:
            self.query_one("#report", Container).loading = False

    def _populate(self, rows: list[ClientRow]) -> None:
        """Fill the clients DataTable from the loaded rows."""
        t = i18n.active().t
        self._rows = rows
        table = cast("DataTable[str]", self.query_one("#clients", DataTable))
        table.add_columns(
            t("clients.col.client"),
            t("clients.col.version"),
            t("clients.col.resumable"),
            t("clients.col.default"),
        )
        table.add_rows((row.client, row.version, row.resumable, row.default) for row in rows)
        self.query_one("#report", Container).loading = False

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Follow the cursor: show the highlighted client's resume caveat, if it has one.

        Enter does not move the cursor, so a confirmation written by a switch survives until
        the user moves on -- the same one-shot behaviour the menu screens' flash has.
        """
        if 0 <= event.cursor_row < len(self._rows):
            self.query_one("#detail", Static).update(self._rows[event.cursor_row].note)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Make the selected client the default: persist it, move the marker, confirm."""
        apply = self.menu_app.set_default_client
        if apply is None or not 0 <= event.cursor_row < len(self._rows):
            return
        row = self._rows[event.cursor_row]
        result = apply(row.name)
        detail = self.query_one("#detail", Static)
        if not result.ok:  # defensive: the rows are the supported clients, so always valid
            detail.update(f"✗ {result.message}")
            return
        # Keep the app's notion of the default in step, so the resume picker's "will launch
        # on <client>" notes stay honest for the rest of this menu session.
        self.menu_app.current_client = row.name
        self._mark_default(row.name)
        detail.update(f"✓ {result.message}")

    def _mark_default(self, name: str) -> None:
        """Move the default marker onto the newly chosen client's row (in place)."""
        marker = i18n.active().t("clients.default_marker")
        table = cast("DataTable[str]", self.query_one("#clients", DataTable))
        for index, row in enumerate(self._rows):
            value = marker if row.name == name else ""
            table.update_cell_at(Coordinate(index, self._DEFAULT_COLUMN), value)

    def action_back(self) -> None:
        """Pop back to the Config menu."""
        self.menu_app.pop_screen()


class ConfigListScreen(Screen[None]):
    """Read-only table of every setting: key · value · default · type.

    The bulk overview ``gmlw config list`` prints, as a DataTable — complements Get's
    filter-to-one. Reads the already-injected settings synchronously (no worker). Esc goes back.
    """

    BINDINGS: ClassVar[list[Binding]] = [_key("escape", "back", "tui.key.back")]

    @property
    def menu_app(self) -> MenuApp:
        """The owning app, narrowed from Textual's generic ``App`` to :class:`MenuApp`."""
        return cast("MenuApp", self.app)  # pyright: ignore[reportUnknownMemberType]

    @property
    def _config(self) -> ConfigCatalog:
        return cast("ConfigCatalog", self.menu_app.config)  # pushed only when wired

    def compose(self) -> ComposeResult:
        """A breadcrumb, the settings table, and the key hints."""
        t = i18n.active().t
        yield Static(f"{self._config.crumb} > {t('tui.cfg.list')}", id="crumb")
        with Container(id="report"):
            yield DataTable(id="settings", cursor_type="row", zebra_stripes=True)
        yield Static(t("tui.export.keys"), id="keys")

    def on_mount(self) -> None:
        """Fill the settings table from the injected config catalog."""
        t = i18n.active().t
        table = cast("DataTable[str]", self.query_one("#settings", DataTable))
        table.add_columns(
            t("tui.cfg.col.key"),
            t("tui.cfg.col.value"),
            t("tui.cfg.col.default"),
            t("tui.cfg.col.type"),
        )
        for setting in self._config.settings:
            table.add_row(setting.key, setting.value, setting.default, setting.type_name)

    def action_back(self) -> None:
        """Pop back to the Config menu."""
        self.menu_app.pop_screen()


class RulesMenuScreen(_MenuScreen):
    """The rule axes that actually hold rules — nothing to walk into that would be empty.

    A user with no rules yet sees the empty hint rather than two barren branches, because
    rules are not authored here: they are captured mid-session, active immediately, and land
    under the environment in play or the role being worn.
    """

    empty_key = "tui.rules.none"

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Rules (localised)."""
        return f"gmlw > {i18n.active().t('tui.rules')}"

    def menu_items(self) -> list[_Item]:
        """One row per axis holding at least one populated group."""
        t = i18n.active().t
        rows: list[_Item] = []
        for axis in RuleAxis:
            groups = [g for g in self.menu_app.rule_groups() if g.axis is axis]
            if not groups:
                continue
            drafts = sum(g.draft_count for g in groups)
            rows.append(
                _Item(
                    _AXIS_ICON[axis],
                    t(f"tui.rules.axis.{axis.value}"),
                    t(f"tui.rules.axis.{axis.value}.d"),
                    f"rules:axis:{axis.value}",
                    note=t("tui.rules.drafts", count=drafts) if drafts else "",
                )
            )
        return rows

    def handle(self, item: _Item) -> None:
        """Open the chosen axis's groups."""
        _, _, value = item.action.rpartition(":")
        self.menu_app.push_screen(RuleAxisScreen(RuleAxis(value)))


class RuleAxisScreen(_MenuScreen):
    """The environments (or roles) on one axis that hold rules."""

    empty_key = "tui.rules.none"

    def __init__(self, axis: RuleAxis) -> None:
        """Bind the screen to the axis whose groups it lists.

        Args:
            axis: The axis to browse.
        """
        super().__init__()
        self._axis = axis

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Rules > <axis>."""
        t = i18n.active().t
        return f"gmlw > {t('tui.rules')} > {t(f'tui.rules.axis.{self._axis.value}')}"

    def menu_items(self) -> list[_Item]:
        """One row per populated group on this axis, labelled as the user named it."""
        t = i18n.active().t
        return [
            _Item(
                _AXIS_ICON[group.axis],
                group.label,
                t("tui.rules.count", count=len(group.rules)),
                f"rules:group:{group.slug}",
                note=t("tui.rules.drafts", count=group.draft_count) if group.draft_count else "",
            )
            for group in self.menu_app.rule_groups()
            if group.axis is self._axis
        ]

    def handle(self, item: _Item) -> None:
        """Open the chosen group's rules."""
        _, _, slug = item.action.rpartition(":")
        group = next(
            (g for g in self.menu_app.rule_groups() if g.axis is self._axis and g.slug == slug),
            None,
        )
        if group is not None:
            self.menu_app.push_screen(RuleListScreen(group))


class RuleListScreen(_MenuScreen):
    """One group's rules. Read-only: the detail panel shows the highlighted rule.

    A rule is active from creation; a draft is one the user has since switched off, and it
    is injected into no session. Both are listed and distinguished, because "which of these
    is actually live" is the question this screen exists to answer.
    """

    empty_key = "tui.rules.none"

    def __init__(self, group: RuleGroup) -> None:
        """Bind the screen to the group whose rules it lists.

        Args:
            group: The environment or role to browse.
        """
        super().__init__()
        self._group = group

    def header_text(self) -> str:
        """Breadcrumb: gmlw > Rules > <axis> > <group label>."""
        t = i18n.active().t
        axis = t(f"tui.rules.axis.{self._group.axis.value}")
        return f"gmlw > {t('tui.rules')} > {axis} > {self._group.label}"

    def menu_items(self) -> list[_Item]:
        """One row per rule: its slug, the instruction itself, and its status."""
        t = i18n.active().t
        rows: list[_Item] = []
        for rule in self._group.rules:
            status = t("tui.rules.draft") if rule.draft else t("tui.rules.active")
            if rule.strength:
                status = f"{status} · {rule.strength}"
            rows.append(
                _Item(
                    "📝" if rule.draft else "📏",
                    rule.slug,
                    rule.rule or t("tui.rules.norule"),
                    "rules:rule",
                    note=f"{status}\n{rule.when}" if rule.when else status,
                )
            )
        return rows

    def handle(self, item: _Item) -> None:
        """Rules are read-only here; the detail panel already shows the selection."""


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
    #banner { padding: 1 1 0 1; height: auto; }  /* the Rich Panel carries its own colour */
    #crumb  { dock: top; padding: 0 1; color: $text-muted; }
    #name   { margin: 1 2; }
    #menu   { height: 1fr; background: transparent; }
    #empty  { height: 1fr; padding: 1 2; color: $text-muted; }
    #report  { height: 1fr; padding: 0 1; }
    #summary { height: auto; padding: 1 0; }
    .section { text-style: bold; padding: 1 0 0 0; color: $text-muted; }
    #models, #sessions, #clients,
    #settings, #session_table { height: auto; max-height: 20; margin: 0 0 1 0; }
    #status_line { padding: 1 1; }
    #consequences { height: 1fr; padding: 1 2; }
    #status { dock: bottom; height: auto; }
    #detail { padding: 1 1; min-height: 2; height: auto; color: $text-muted; }
    #keys   { padding: 0 1; color: $text-muted; }
    ListItem { height: auto; padding: 0 1; background: transparent; }
    ListView > ListItem.-highlight { background: cyan 15%; }
    ListView:focus > ListItem.-highlight { background: cyan 25%; color: $text; }
    /* The settings picker drives its list from a focused Input, so the ListView itself never
       holds focus and the rule above never fires -- the cursored row read as unselected, and
       the first Down looked like it skipped a row. Highlight it at focused strength there. */
    ConfigPickerScreen ListView > ListItem.-highlight { background: cyan 25%; color: $text; }
    """
    TITLE = "gmlw"

    def __init__(  # noqa: PLR0913  (the app's injection seam: one kwarg per browser's data)
        self,
        jobs: list[JobChoice],
        *,
        switchers: dict[str, Switcher] | None = None,
        validate_job: Callable[[str], str | None] | None = None,
        validate_workflow: Callable[[str], str | None] | None = None,
        sessions_for: Callable[[str], list[SessionChoice]] | None = None,
        usage_view: Callable[[str], UsageView] | None = None,
        save_usage: Callable[[str], str] | None = None,
        workflows: list[Workflow] | None = None,
        rules: Callable[[], tuple[RuleGroup, ...]] | None = None,
        clients: Callable[[], list[ClientRow]] | None = None,
        set_default_client: Callable[[str], ConfigSetResult] | None = None,
        config: ConfigCatalog | None = None,
        current_client: str = "",
        deleter: Deleter | None = None,
        reload_jobs: Callable[[], list[JobChoice]] | None = None,
        archiver: Archiver | None = None,
        launch_clients: Callable[[], list[ClientChoice]] | None = None,
    ) -> None:
        """Bind the injected data the browsers read from and the callbacks they invoke.

        Args:
            jobs: The resumable jobs the Resume picker lists.
            switchers: The config switchers, keyed by ``persona`` / ``environment`` /
                ``role``. Each carries its options, current value, and a setter. A missing
                key just leaves that Config verb stubbed, so the app runs unwired in tests.
            validate_job: Validates a typed new-job name, returning an error message or
                ``None`` when it is acceptable; defaults to accepting anything (tests).
            validate_workflow: Validates a typed new-workflow name (empty ⇒ named at the end),
                returning an error message or ``None``; defaults to accepting anything.
            sessions_for: Lists a job's sessions for the session picker (lazily, per job);
                defaults to none.
            usage_view: Builds a job's usage summary (totals + by-model + by-session rows) for
                the Export view (lazily, per job, on a worker thread); defaults to empty.
            save_usage: Writes a job's full report to a file and returns the path, for the
                save-to-file Export destination (lazily, per job); defaults to a no-op.
            workflows: The runnable workflows (slug + label + description), for the Workflow
                Run/List/Edit/Export screens; the pickers show the label and carry the slug.
                Defaults to none.
            rules: Lists the environments and roles holding rules, for the Rules browser;
                read once on first use and cached, so walking the tree never re-reads disk.
                Defaults to none, so the app runs unwired in tests.
            clients: Lists the supported clients + versions for the Config Clients view (on a
                worker thread); ``None`` leaves that verb stubbed, so the app runs unwired.
            set_default_client: Writes the default client picked in the Clients view; ``None``
                leaves that view read-only, so the app runs unwired in tests.
            config: The settings + setter the Config Get/Set browsers read and call; ``None``
                leaves those two Config verbs stubbed, so the app runs unwired in tests.
            current_client: The user's default client, to flag when a session's client
                differs (resuming will launch the session's client, not this one).
            deleter: Previews and performs the removals the Delete screens offer; ``None``
                leaves them read-only, so the app runs unwired in tests.
            reload_jobs: Re-reads the job list after a delete has changed it. Only the job
                list needs this -- sessions are already read per job through
                ``sessions_for``, so they refresh on their own. Defaults to keeping the
                list as-is.
            archiver: Exports a workflow and installs one from an archive; ``None`` leaves
                both verbs read-only, so the app runs unwired in tests.
            launch_clients: The clients a launch can be pointed at, re-read each time the
                picker opens (so a default changed in Config shows immediately). Defaults
                to none, which skips the picker entirely and launches on the configured
                default -- the behaviour before the picker existed.
        """
        super().__init__()
        self.jobs = jobs
        self.switchers = switchers or {}
        self.validate_job = validate_job or _accept_any_job
        self.validate_workflow = validate_workflow or _accept_any_workflow
        self.sessions_for = sessions_for or _no_sessions
        self.usage_view = usage_view or _no_usage_view
        self.save_usage = save_usage or _no_save
        self.workflows = workflows or []
        self.rules = rules or _no_rules
        self._rule_cache: tuple[RuleGroup, ...] | None = None
        self.clients = clients
        self.set_default_client = set_default_client
        self.config = config
        self.current_client = current_client
        self.deleter = deleter
        self._reload_jobs = reload_jobs
        self.archiver = archiver
        self.launch_clients = launch_clients or _no_clients

    def refresh_jobs(self) -> None:
        """Re-read the job list after something changed it (a delete)."""
        if self._reload_jobs is not None:
            self.jobs = self._reload_jobs()

    def refresh_workflows(self) -> None:
        """Re-read the workflow catalogue after an import added or replaced one."""
        if self.archiver is not None:
            self.workflows = self.archiver.reload_workflows()

    def rule_groups(self) -> tuple[RuleGroup, ...]:
        """The populated rule groups, read once and cached for the app's lifetime.

        Cached because every screen in the Rules tree asks for the whole catalogue to
        filter it, and re-walking the rule folders on each cursor move would put disk I/O
        on the keystroke path.

        Returns:
            Every environment and role holding at least one rule.
        """
        if self._rule_cache is None:
            self._rule_cache = self.rules()
        return self._rule_cache

    def launch(self, pending: MenuChoice) -> None:
        """Finish a launch: ask which client to run it on, then exit with the answer.

        The one place the client step is inserted, so every launcher gets it by handing
        its choice here instead of exiting itself. With nothing to choose between (the app
        unwired, or no client detected) it exits straight away and the wiring falls back to
        the configured default -- the behaviour before the picker existed.
        """
        if self.launch_clients():
            self.push_screen(ClientPickerScreen(pending))
        else:
            self.exit(pending)

    def tell_current(self, message: str) -> None:
        """Show ``message`` on whichever menu screen is now on top, if any.

        Used when a screen removed the last of what it was showing and stepped back out:
        the outcome belongs to the screen the user lands on, not the one that is gone.
        """
        for screen in reversed(self.screen_stack):
            if isinstance(screen, _MenuScreen):
                screen.tell(message)
                return

    def on_mount(self) -> None:
        """Open on the top (object) menu."""
        self.push_screen(TopMenuScreen())
