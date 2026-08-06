# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for clean exit handling (no tracebacks) and the farewell line."""

import argparse
import io

import pytest

from generic_ml_wrapper.adapter.inbound.cli import app
from generic_ml_wrapper.application.port.inbound.start_job_result import StartJobResult


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


def test_farewell_is_the_same_line_for_everyone() -> None:
    """No companion check: a goodbye is a label, and everyone gets it."""
    assert app._farewell() == "Bye."


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
    monkeypatch.setattr(app, "build_compose_statusline", _boom_statusline_builder)
    assert app._statusline() == 0
    out = capsys.readouterr().out
    assert out == "\n"  # one empty line, never a traceback
