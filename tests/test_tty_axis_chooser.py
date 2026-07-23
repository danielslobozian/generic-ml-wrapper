# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the TTY axis chooser: a menu of examples plus a "type your own" path."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap import tty_axis_chooser, tty_prompt
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_axis_chooser import TtyAxisChooser
from generic_ml_wrapper.application.domain.model.axis import ENVIRONMENT_PROMPT
from generic_ml_wrapper.common.i18n import load_localizer

if TYPE_CHECKING:
    import pytest


class _Tty(io.StringIO):
    """A StringIO that claims to be a terminal."""

    def isatty(self) -> bool:
        return True


def _wire(monkeypatch: pytest.MonkeyPatch, *, stdin: str, tty: bool = True) -> io.StringIO:
    """Point both the menu primitive and the chooser at a scripted stdin + captured stderr."""
    stdin_stream: io.StringIO = _Tty(stdin) if tty else io.StringIO(stdin)
    err: io.StringIO = _Tty() if tty else io.StringIO()
    for module in (tty_prompt, tty_axis_chooser):
        monkeypatch.setattr(module.sys, "stdin", stdin_stream)
        monkeypatch.setattr(module.sys, "stderr", err)
    return err


def _chooser() -> TtyAxisChooser:
    return TtyAxisChooser(load_localizer("en"))


def test_picking_a_menu_example_returns_its_canonical_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="1\n")  # the first environment example is "work"
    selection = _chooser().choose(ENVIRONMENT_PROMPT, "work", load_localizer("en"))
    assert (selection.slug, selection.label) == ("work", "Work")


def test_type_your_own_slugifies_the_answer_and_echoes_it(monkeypatch: pytest.MonkeyPatch) -> None:
    # 4 examples + "type your own" = option 5; then a free-text French answer.
    err = _wire(monkeypatch, stdin="5\nÉquipe Produit\n")
    selection = _chooser().choose(ENVIRONMENT_PROMPT, "work", load_localizer("en"))
    assert selection.slug == "equipe-produit"  # accents stripped, kebab-cased
    assert selection.label == "Équipe Produit"  # the human wording is kept as the label
    assert "equipe-produit" in err.getvalue()  # the alias is echoed back


def test_non_tty_declines_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="1\n", tty=False)
    selection = _chooser().choose(ENVIRONMENT_PROMPT, "work", load_localizer("en"))
    assert (selection.slug, selection.label, selection.description) == ("work", "work", "work")


def test_empty_typed_answer_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="5\n\n")  # choose "type your own", then an empty line
    selection = _chooser().choose(ENVIRONMENT_PROMPT, "work", load_localizer("en"))
    assert selection.slug == "work"
