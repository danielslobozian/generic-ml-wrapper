# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests: the launch banner derives its version and client list (no drift)."""

from __future__ import annotations

from rich.console import Console

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.inbound.tui.banner import boxed_banner
from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.common import i18n


def _render() -> list[str]:
    """Render the banner Panel to plain text lines (colour stripped, trailing space trimmed)."""
    i18n.set_active(i18n.load_localizer("en"))
    console = Console(width=80, no_color=True)
    with console.capture() as capture:
        console.print(boxed_banner())
    return [line.rstrip() for line in capture.get().splitlines() if line.strip()]


def test_banner_shows_derived_version_and_every_client() -> None:
    text = "\n".join(_render())
    assert f"v{__version__}" in text
    for info in client_catalog.SUPPORTED:
        assert info.name in text


def test_banner_is_a_closed_rounded_box_with_aligned_rows() -> None:
    lines = _render()
    assert lines[0].startswith("╭")
    assert lines[0].endswith("╮")
    assert lines[-1].startswith("╰")
    assert lines[-1].endswith("╯")
    assert len({len(line) for line in lines}) == 1  # every row the same width -> a straight frame


def test_banner_tagline_is_localised() -> None:
    try:
        i18n.set_active(i18n.load_localizer("fr"))
        console = Console(width=80, no_color=True)
        with console.capture() as capture:
            console.print(boxed_banner())
        assert "compagnon" in capture.get()  # the French tagline, not the English one
    finally:
        i18n.set_active(i18n.load_localizer("en"))  # don't leak fr into other tests' assertions
