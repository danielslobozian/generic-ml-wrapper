# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Config > Status line: show, hide and reorder the status line's blocks.

Two tabs -- the live line, and the session/job rows under it. In each, ``space`` shows or
hides the highlighted block and ``shift+↑↓`` moves it; on the rows tab, ``a`` turns the
agents' share after a field on or off. Every change is saved at once, like the other
Config browsers: there is no separate save step to forget.

Like :mod:`menu_app`, this module is free of use cases and ports: it is handed a
:class:`StatuslineSettings` bundle (load + save) by the wiring. Its footer labels are
resolved at import, so it must be imported after the active localiser is installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, Static, TabbedContent, TabPane

from generic_ml_wrapper.application.domain.model.statusline_layout import (
    AGENT_FIELDS,
    LINE_BLOCKS,
    ROW_FIELDS,
    StatuslineLayout,
)
from generic_ml_wrapper.common import i18n

if TYPE_CHECKING:
    from collections.abc import Callable

    from textual.app import App, ComposeResult

_SHOWN, _HIDDEN = "☑", "☐"
# The two tabs, by the id of the list each holds.
_LINE, _ROWS = "sl_line", "sl_rows"


@dataclass(frozen=True)
class StatuslineSettings:
    """The status line's layout as the wiring reads and saves it."""

    load: Callable[[], StatuslineLayout]
    save: Callable[[StatuslineLayout], None]


def _binding(key: str, action: str, label: str) -> Binding:
    """A key binding whose footer label comes from the catalogue."""
    return Binding(key, action, i18n.active().t(label))


@dataclass
class _Block:
    """One row of a tab: a block's name and whether it is shown."""

    name: str
    shown: bool


def _ordered(shown: tuple[str, ...], every: tuple[str, ...]) -> list[_Block]:
    """The shown blocks in their order, then the hidden ones in their default order."""
    return [_Block(name, True) for name in shown] + [
        _Block(name, False) for name in every if name not in shown
    ]


class StatuslineScreen(Screen[None]):
    """Show, hide and reorder the status line's blocks, saved as they change."""

    BINDINGS: ClassVar[list[Binding]] = [
        _binding("escape", "back", "tui.key.back"),
        _binding("space", "show_hide", "tui.key.toggle"),
        _binding("a", "agents", "tui.sl.key.agents"),
        _binding("shift+up", "move(-1)", "tui.sl.key.up"),
        _binding("shift+down", "move(1)", "tui.sl.key.down"),
        _binding("left", "tab(-1)", "tui.sl.key.tab"),
        _binding("right", "tab(1)", "tui.sl.key.tab"),
    ]

    def __init__(self, settings: StatuslineSettings) -> None:
        """Bind the screen to the layout it edits."""
        super().__init__()
        self._settings = settings
        layout = settings.load()
        self._entries: dict[str, list[_Block]] = {
            _LINE: _ordered(layout.line, LINE_BLOCKS),
            _ROWS: _ordered(layout.rows, ROW_FIELDS),
        }
        self._agents = set(layout.agents)

    @property
    def _app(self) -> App[object]:
        """The owning app, narrowed from Textual's partially-typed generic ``App``."""
        return cast("App[object]", self.app)  # pyright: ignore[reportUnknownMemberType]

    def compose(self) -> ComposeResult:
        """A breadcrumb, the two tabs, then the docked detail + key bar."""
        t = i18n.active().t
        yield Static(f"gmlw > {t('tui.config')} > {t('tui.cfg.statusline')}", id="crumb")
        with TabbedContent(id="sl_tabs"):
            with TabPane(t("tui.sl.tab.line"), id=f"{_LINE}_tab"):
                yield ListView(*self._items(_LINE), id=_LINE)
            with TabPane(t("tui.sl.tab.rows"), id=f"{_ROWS}_tab"):
                yield ListView(*self._items(_ROWS), id=_ROWS)
        with Container(id="status"):
            yield Static("", id="detail")
            yield Static(t("tui.sl.keys"), id="keys")

    def on_mount(self) -> None:
        """Start in the live line's list, its first block described."""
        self.query_one(f"#{_LINE}", ListView).focus()
        self._describe()

    def _items(self, tab: str) -> list[ListItem]:
        return [ListItem(Label(self._text(tab, index))) for index in range(len(self._entries[tab]))]

    def _text(self, tab: str, index: int) -> str:
        """One row: its shown box and name, then -- for a field that has one -- its agents box."""
        t = i18n.active().t
        block = self._entries[tab][index]
        text = f"{_SHOWN if block.shown else _HIDDEN} {t(f'tui.sl.block.{block.name}')}"
        if tab == _ROWS and block.name in AGENT_FIELDS:
            box = _SHOWN if block.name in self._agents else _HIDDEN
            text = f"{text:<24}{t('tui.sl.agents')} {box}"
        return text

    def _tab(self) -> str:
        """The list of the tab in front."""
        active = self.query_one("#sl_tabs", TabbedContent).active
        return _ROWS if active.startswith(_ROWS) else _LINE

    def _list(self) -> ListView:
        return self.query_one(f"#{self._tab()}", ListView)

    def _repaint(self, tab: str) -> None:
        """Re-render every row of ``tab`` in place, so the cursor stays put."""
        for index, item in enumerate(self.query_one(f"#{tab}", ListView).query(ListItem)):
            item.query_one(Label).update(self._text(tab, index))

    def _describe(self, message: str = "") -> None:
        """Show the highlighted block's description, or ``message`` when there is one."""
        index = self._list().index
        if message or index is None:
            self.query_one("#detail", Static).update(message)
            return
        name = self._entries[self._tab()][index].name
        self.query_one("#detail", Static).update(i18n.active().t(f"tui.sl.block.{name}.d"))

    def on_list_view_highlighted(self, _event: ListView.Highlighted) -> None:
        """Follow the cursor with the description."""
        self._describe()

    def on_tabbed_content_tab_activated(self, _event: TabbedContent.TabActivated) -> None:
        """Keep the keys working after a tab is clicked: focus that tab's list."""
        self._list().focus()
        self._describe()

    def action_tab(self, step: int) -> None:  # noqa: ARG002  (two tabs: either way flips)
        """Bring the other tab to the front."""
        other = _LINE if self._tab() == _ROWS else _ROWS
        self.query_one("#sl_tabs", TabbedContent).active = f"{other}_tab"

    def action_show_hide(self) -> None:
        """Show or hide the highlighted block."""
        tab, index = self._tab(), self._list().index
        if index is None:
            return
        block = self._entries[tab][index]
        block.shown = not block.shown
        self._repaint(tab)
        self._save()

    def action_agents(self) -> None:
        """Turn the agents' share after the highlighted field on or off (rows tab only)."""
        tab, index = self._tab(), self._list().index
        if tab != _ROWS or index is None:
            return
        name = self._entries[tab][index].name
        if name not in AGENT_FIELDS:
            self._describe(i18n.active().t("tui.sl.no_agents"))
            self._app.bell()
            return
        self._agents ^= {name}
        self._repaint(tab)
        self._save()

    def action_move(self, step: int) -> None:
        """Move the highlighted block one place up (``-1``) or down (``1``) in its tab."""
        tab, view = self._tab(), self._list()
        index = view.index
        entries = self._entries[tab]
        if index is None or not 0 <= index + step < len(entries):
            return
        entries[index], entries[index + step] = entries[index + step], entries[index]
        self._repaint(tab)
        view.index = index + step
        self._save()

    def _layout(self) -> StatuslineLayout:
        def shown(tab: str) -> tuple[str, ...]:
            return tuple(block.name for block in self._entries[tab] if block.shown)

        return StatuslineLayout(shown(_LINE), shown(_ROWS), frozenset(self._agents))

    def _save(self) -> None:
        """Persist the layout as it now stands; say so only when it could not be written."""
        try:
            self._settings.save(self._layout())
        except OSError as error:
            self._describe(i18n.active().t("tui.sl.save_failed", error=error))
            return
        self._describe()

    def action_back(self) -> None:
        """Pop back to the Config menu."""
        self._app.pop_screen()
