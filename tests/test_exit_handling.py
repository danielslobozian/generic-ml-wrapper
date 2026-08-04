# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for clean exit handling (no tracebacks) and the farewell line."""

import argparse
import io
import signal

import pytest

from generic_ml_wrapper.adapter.inbound.cli import app
from generic_ml_wrapper.adapter.outbound.config import toml_config_reader
from generic_ml_wrapper.adapter.outbound.config.toml_config_reader import CompanionSettings
from generic_ml_wrapper.application.port.inbound.start_job import StartJobResult


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
    monkeypatch.setattr(
        toml_config_reader, "companion", lambda: CompanionSettings(persona=None, name=None)
    )
    assert app._farewell() is None


def test_farewell_greets_the_configured_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        toml_config_reader, "companion", lambda: CompanionSettings(persona="butler", name="Ada")
    )
    assert app._farewell() == "Bye, Ada."


def _noop_signal(*_args: object) -> None:
    return None


def _true() -> bool:
    return True


def _true_for_client(_client: object) -> bool:
    return True


class _TerminatedStartJob:
    """A client that was killed by SIGTERM: the run returns, it does not raise."""

    def execute(self, _command: object) -> object:
        return StartJobResult(exit_code=143, job="test", session_id="test_001")


def test_client_owns_interrupts_only_takes_the_interrupt() -> None:
    # A kill is not handled here: the caller adapter forwards it to the client it
    # launched, so this must leave the termination disposition exactly as it found it.
    before_int = signal.getsignal(signal.SIGINT)
    before_term = signal.getsignal(signal.SIGTERM)
    with app._client_owns_interrupts():
        assert signal.getsignal(signal.SIGINT) is app._ignore_sigint
        assert signal.getsignal(signal.SIGTERM) is before_term
    assert signal.getsignal(signal.SIGINT) is before_int
    assert signal.getsignal(signal.SIGTERM) is before_term


def test_a_terminated_client_reports_128_plus_the_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "_preflight_cwd", _true)
    monkeypatch.setattr(app, "_preflight_client", _true_for_client)
    monkeypatch.setattr(app, "build_start_job", _TerminatedStartJob)
    args = argparse.Namespace(
        job="test", client="claude", workflow=None, resume_latest=False, client_args=None
    )
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
