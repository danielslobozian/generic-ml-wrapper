# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the terminal client chooser."""

import io

import pytest

from generic_ml_wrapper.adapter.outbound.bootstrap import tty_prompt
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_client_chooser import TtyClientChooser
from generic_ml_wrapper.common.i18n import load_localizer

_I18N = load_localizer("en")


class _Tty(io.StringIO):
    """A StringIO that claims to be a terminal."""

    def isatty(self) -> bool:
        return True


def _wire(monkeypatch: pytest.MonkeyPatch, *, stdin: str, tty: bool = True) -> io.StringIO:
    """Point the shared prompt's stdin/stderr at fakes; return the captured stderr."""
    stdin_stream: io.StringIO = _Tty(stdin) if tty else io.StringIO(stdin)
    err: io.StringIO = _Tty() if tty else io.StringIO()
    monkeypatch.setattr(tty_prompt.sys, "stdin", stdin_stream)
    monkeypatch.setattr(tty_prompt.sys, "stderr", err)
    return err


def test_declines_when_not_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="1\n", tty=False)
    assert TtyClientChooser(_I18N).choose(["claude", "cursor"]) is None


def test_empty_line_takes_the_first_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    err = _wire(monkeypatch, stdin="\n")
    assert TtyClientChooser(_I18N).choose(["claude", "cursor"]) == "claude"
    prompt = err.getvalue()
    assert "1) claude" in prompt
    assert "2) cursor" in prompt


def test_a_number_selects_that_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="2\n")
    assert TtyClientChooser(_I18N).choose(["claude", "cursor", "codex"]) == "cursor"


def test_reprompts_on_an_out_of_range_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    err = _wire(monkeypatch, stdin="9\nfoo\n2\n")
    assert TtyClientChooser(_I18N).choose(["claude", "cursor"]) == "cursor"
    assert "not one of 1-2" in err.getvalue()


def test_declines_on_end_of_input(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="")  # EOF immediately
    assert TtyClientChooser(_I18N).choose(["claude", "cursor"]) is None
