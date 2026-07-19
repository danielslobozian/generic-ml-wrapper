# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the guided-vs-quick authoring chooser."""

import io

import pytest

from generic_ml_wrapper.adapter.outbound.bootstrap import tty_prompt
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_guided_chooser import (
    GUIDED,
    QUICK,
    TtyGuidedChooser,
)
from generic_ml_wrapper.common.i18n import load_localizer

_I18N = load_localizer("en")


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
    assert TtyGuidedChooser(_I18N).choose() is None  # caller falls back to lean


def test_enter_picks_the_guided_experience(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="\n")  # empty line takes the default (index 0)
    assert TtyGuidedChooser(_I18N).choose() == GUIDED


def test_picks_quick_when_chosen(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="2\n")
    assert TtyGuidedChooser(_I18N).choose() == QUICK


def test_picks_guided_when_chosen(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="1\n")
    assert TtyGuidedChooser(_I18N).choose() == GUIDED
