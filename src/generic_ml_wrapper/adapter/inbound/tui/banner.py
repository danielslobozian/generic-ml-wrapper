# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The launch banner for the interactive menu.

A compact Rich panel: the ``gmlw`` wordmark as a cyan→indigo gradient in the title with a
dimmed, localised tagline beside it, and the supported clients (left) with the version
(right) inside a rounded box. Version and client list are *derived* — from the package
version and the client catalog — so the banner can never drift from what the tool actually
is. Returned as a Rich renderable for a Textual ``Static``; the colour is baked into the
renderable (per-letter gradient), not the stylesheet.
"""

from __future__ import annotations

from rich import box
from rich.panel import Panel
from rich.text import Text

from generic_ml_wrapper import __version__
from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.common import i18n

# The wordmark, coloured letter-by-letter (cyan → indigo). One colour per character.
_WORDMARK = "gmlw"
_GRADIENT = ("#22d3ee", "#46bff2", "#64a6f5", "#818cf8")


def _clients_line() -> str:
    """The supported clients, joined for the banner's footer (e.g. ``claude · cursor``)."""
    return " · ".join(info.name for info in client_catalog.SUPPORTED)


def _wordmark() -> Text:
    """Render ``gmlw`` as a bold per-letter gradient."""
    text = Text()
    for char, colour in zip(_WORDMARK, _GRADIENT, strict=True):
        text.append(char, style=f"bold {colour}")
    return text


def boxed_banner() -> Panel:
    """Render the wordmark + tagline in a rounded box, clients (left) and version (right).

    Returns:
        A Rich :class:`~rich.panel.Panel`, ready to drop into a Textual ``Static``.
    """
    title = _wordmark()
    title.append("  ")
    title.append(i18n.t("banner.tagline"), style="dim italic")
    body = Text()
    body.append(_clients_line(), style="cyan")
    body.append("   ·   ", style="dim")
    body.append(f"v{__version__}", style="bold")
    return Panel(
        body,
        title=title,
        title_align="left",
        box=box.ROUNDED,
        border_style="grey42",
        padding=(0, 1),
        expand=False,
    )
