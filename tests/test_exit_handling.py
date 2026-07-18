# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for clean exit handling (no tracebacks) and the farewell line."""

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
