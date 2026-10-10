# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the terminal persona chooser."""

import io

import pytest

from generic_ml_wrapper.adapter.outbound.bootstrap import tty_prompt
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_persona_chooser import TtyPersonaChooser
from generic_ml_wrapper.application.domain.model.persona import Persona
from generic_ml_wrapper.common.i18n import load_localizer

_I18N = load_localizer("en")
_PERSONAS = [Persona("plain", "Neutral.", "", "b"), Persona("butler", "A Jeeves.", "", "b")]


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def _wire(monkeypatch: pytest.MonkeyPatch, *, stdin: str, tty: bool = True) -> io.StringIO:
    stdin_stream: io.StringIO = _Tty(stdin) if tty else io.StringIO(stdin)
    err: io.StringIO = _Tty() if tty else io.StringIO()
    monkeypatch.setattr(tty_prompt.sys, "stdin", stdin_stream)
    monkeypatch.setattr(tty_prompt.sys, "stderr", err)
    return err


def test_declines_when_not_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="1\n", tty=False)
    assert TtyPersonaChooser(_I18N).choose(_PERSONAS) is None


def test_declines_when_no_personas(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="1\n")
    assert TtyPersonaChooser(_I18N).choose([]) is None


def test_empty_line_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    err = _wire(monkeypatch, stdin="\n")
    assert TtyPersonaChooser(_I18N).choose(_PERSONAS) is None  # skip -> companion off
    assert "A Jeeves." in err.getvalue()  # descriptions were shown


def test_a_number_selects_that_persona(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="2\n")
    assert TtyPersonaChooser(_I18N).choose(_PERSONAS) == "butler"


def test_reprompts_on_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    err = _wire(monkeypatch, stdin="9\n1\n")
    assert TtyPersonaChooser(_I18N).choose(_PERSONAS) == "plain"
    assert "not one of 1-2" in err.getvalue()


def test_declines_on_end_of_input(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="")
    assert TtyPersonaChooser(_I18N).choose(_PERSONAS) is None


def test_shipped_descriptions_speak_the_chosen_language(monkeypatch: pytest.MonkeyPatch) -> None:
    # Issue #87: the first-run wizard in French listed the personas in English.
    shipped = Persona(
        "butler",
        "A characterful Jeeves — formal, anticipatory, dryly witty, unflappable.",
        "",
        "b",
    )
    edited = Persona("plain", "My own plain words.", "", "b")
    err = _wire(monkeypatch, stdin="\n")
    TtyPersonaChooser(load_localizer("fr")).choose([shipped, edited])
    shown = err.getvalue()
    assert "Un Jeeves plein de caractère" in shown
    assert "Jeeves — formal" not in shown
    assert "My own plain words." in shown  # an edited description is the user's own
