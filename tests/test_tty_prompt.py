# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the shared numbered terminal chooser."""

import io

import pytest

from generic_ml_wrapper.adapter.outbound.bootstrap import tty_prompt
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_prompt import Choice, choose_number
from generic_ml_wrapper.common.i18n import load_localizer

_I18N = load_localizer("en")
_CHOICES = [Choice("a", "Alpha"), Choice("b", "Beta", icon="✨", description="the second")]


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def _run(
    monkeypatch: pytest.MonkeyPatch,
    stdin: str,
    *,
    tty: bool = True,
    **kwargs: object,
) -> tuple[str | None, str]:
    stdin_stream: io.StringIO = _Tty(stdin) if tty else io.StringIO(stdin)
    err: io.StringIO = _Tty()
    monkeypatch.setattr(tty_prompt.sys, "stdin", stdin_stream)
    monkeypatch.setattr(tty_prompt.sys, "stderr", err)
    value = choose_number("Header", _CHOICES, _I18N, **kwargs)  # type: ignore[arg-type]
    return value, err.getvalue()


def test_returns_none_when_not_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    value, _ = _run(monkeypatch, "1\n", tty=False, default=0)
    assert value is None


def test_returns_none_with_no_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tty_prompt.sys, "stdin", _Tty("1\n"))
    monkeypatch.setattr(tty_prompt.sys, "stderr", _Tty())
    assert choose_number("H", [], _I18N) is None


def test_a_number_selects_the_value(monkeypatch: pytest.MonkeyPatch) -> None:
    value, _ = _run(monkeypatch, "2\n")
    assert value == "b"


def test_empty_line_takes_the_default_index(monkeypatch: pytest.MonkeyPatch) -> None:
    value, _ = _run(monkeypatch, "\n", default=0)
    assert value == "a"


def test_empty_line_skips_when_skippable(monkeypatch: pytest.MonkeyPatch) -> None:
    value, _ = _run(monkeypatch, "\n", skippable=True)
    assert value is None


def test_reprompts_on_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    value, err = _run(monkeypatch, "9\n1\n")
    assert value == "a"
    assert "not one of 1-2" in err


def test_end_of_input_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    value, _ = _run(monkeypatch, "")
    assert value is None


def test_empty_line_reprompts_when_neither_default_nor_skippable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value, _ = _run(monkeypatch, "\n2\n")  # empty is neither skip nor default -> re-ask
    assert value == "b"


def test_renders_header_numbering_icon_and_description(monkeypatch: pytest.MonkeyPatch) -> None:
    _, err = _run(monkeypatch, "1\n")
    assert "Header" in err
    assert "1) Alpha" in err
    assert "2) ✨  Beta" in err
    assert "the second" in err
