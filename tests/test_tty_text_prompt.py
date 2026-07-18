# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the terminal free-text prompt (name / role / environment)."""

import io

import pytest

from generic_ml_wrapper.adapter.outbound.bootstrap import tty_text_prompt
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_text_prompt import TtyTextPrompt
from generic_ml_wrapper.common.i18n import load_localizer

_I18N = load_localizer("en")


class _Tty(io.StringIO):
    """A StringIO that claims to be a terminal."""

    def isatty(self) -> bool:
        return True


def _wire(monkeypatch: pytest.MonkeyPatch, *, stdin: str, tty: bool = True) -> io.StringIO:
    stdin_stream: io.StringIO = _Tty(stdin) if tty else io.StringIO(stdin)
    err: io.StringIO = _Tty() if tty else io.StringIO()
    monkeypatch.setattr(tty_text_prompt.sys, "stdin", stdin_stream)
    monkeypatch.setattr(tty_text_prompt.sys, "stderr", err)
    return err


def test_returns_default_when_not_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="typed\n", tty=False)
    assert TtyTextPrompt(_I18N).ask("Your name?", "ada") == "ada"


def test_returns_the_typed_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    err = _wire(monkeypatch, stdin="Daniel\n")
    assert TtyTextPrompt(_I18N).ask("Your name?", "ada") == "Daniel"
    rendered = err.getvalue()
    assert "Your name?" in rendered  # the header
    assert "default ada" in rendered  # the localised [default …] fragment


def test_empty_line_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="\n")
    assert TtyTextPrompt(_I18N).ask("Your name?", "ada") == "ada"


def test_trims_surrounding_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="  Daniel  \n")
    assert TtyTextPrompt(_I18N).ask("Your name?", "ada") == "Daniel"


def test_end_of_input_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="")  # EOF
    assert TtyTextPrompt(_I18N).ask("Your name?", "ada") == "ada"


def test_passed_localiser_overrides_the_construction_one(monkeypatch: pytest.MonkeyPatch) -> None:
    err = _wire(monkeypatch, stdin="\n")
    TtyTextPrompt(_I18N).ask("Nom ?", "ada", load_localizer("fr"))
    assert "défaut ada" in err.getvalue()  # the French fragment, not the English one
