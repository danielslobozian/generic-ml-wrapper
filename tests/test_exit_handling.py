# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for clean exit handling (no tracebacks) and the farewell line."""

import argparse
import io
import signal

import pytest

from generic_ml_wrapper.adapter.inbound.cli import app
from generic_ml_wrapper.common.config import CompanionSettings


def test_keyboard_interrupt_exits_130_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupt(_argv: list[str]) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(app, "_dispatch", interrupt)
    assert app.main([]) == 130
    assert "Traceback" not in capsys.readouterr().err


def test_unexpected_error_exits_1_with_a_friendly_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(_argv: list[str]) -> int:
        raise ValueError("kaboom")

    monkeypatch.setattr(app, "_dispatch", boom)
    assert app.main([]) == 1
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "kaboom" in err


def test_ignore_sigint_is_a_noop() -> None:
    assert app._ignore_sigint(2, None) is None


def test_farewell_is_none_without_a_companion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app.config, "companion", lambda: CompanionSettings(persona=None, name=None))
    assert app._farewell() is None


def test_farewell_greets_the_configured_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        app.config, "companion", lambda: CompanionSettings(persona="butler", name="Ada")
    )
    assert app._farewell() == "Bye, Ada."


def _noop_signal(*_args: object) -> None:
    return None


def _true() -> bool:
    return True


def _true_for_client(_client: object) -> bool:
    return True


class _SilentGreeting:
    def execute(self) -> None:
        return None


class _TerminatingStartJob:
    def execute(self, _command: object) -> int:
        raise app._Terminated


def test_on_termination_raises_terminated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app.signal, "signal", _noop_signal)  # don't touch real dispositions
    with pytest.raises(app._Terminated):
        app._on_termination(signal.SIGTERM, None)


def test_client_owns_interrupts_installs_and_restores() -> None:
    before_int = signal.getsignal(signal.SIGINT)
    before_term = signal.getsignal(signal.SIGTERM)
    with app._client_owns_interrupts():
        assert signal.getsignal(signal.SIGINT) is app._ignore_sigint
        assert signal.getsignal(signal.SIGTERM) is app._on_termination
    assert signal.getsignal(signal.SIGINT) is before_int
    assert signal.getsignal(signal.SIGTERM) is before_term


def test_start_returns_143_when_terminated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "_preflight_cwd", _true)
    monkeypatch.setattr(app, "_preflight_client", _true_for_client)
    monkeypatch.setattr(app, "build_render_greeting", _SilentGreeting)
    monkeypatch.setattr(app, "build_start_job", _TerminatingStartJob)
    args = argparse.Namespace(job="test", client="claude", workflow=None, resume_latest=False)
    assert app._start(args) == 143


class _BoomStatusline:
    def execute(self, *_args: object) -> str:
        raise RuntimeError("render blew up")


def _boom_statusline_builder(_client: object) -> _BoomStatusline:
    return _BoomStatusline()


def test_statusline_degrades_to_an_empty_line_on_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    monkeypatch.setattr(app, "build_render_statusline", _boom_statusline_builder)
    assert app._statusline() == 0
    out = capsys.readouterr().out
    assert out == "\n"  # one empty line, never a traceback
