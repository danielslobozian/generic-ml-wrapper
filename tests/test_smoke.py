# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Smoke test: the package imports and its entry point runs."""

import pytest

from generic_ml_wrapper import __version__
from generic_ml_wrapper import main as entry_point
from generic_ml_wrapper.adapter.inbound.common.terminal_valid_actions_policy import (
    TerminalValidActionsPolicy,
)
from generic_ml_wrapper.adapter.outbound.config import toml_config_reader


def test_version_is_a_nonempty_string() -> None:
    assert isinstance(__version__, str)
    assert __version__


def _initialised(*_: object, **__: object) -> str:
    return "0.4.0"  # the gate sees an initialised install


def test_bare_launch_off_a_terminal_is_refused(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Under pytest neither stream is a TTY, which is the piped/scripted case: the entry
    # point refuses before anything else runs, so nothing blocks on a menu.
    monkeypatch.setattr(toml_config_reader, "init_version", _initialised)
    assert entry_point.main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""  # stdout stays clean for whatever is downstream
    assert "gmlw" in captured.err


def test_bare_launch_on_a_terminal_opens_the_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(toml_config_reader, "init_version", _initialised)
    monkeypatch.setattr(TerminalValidActionsPolicy, "_is_interactive", lambda: True)
    opened: list[str] = []

    monkeypatch.setattr(entry_point, "tui_main", lambda: opened.append("menu") or 0)
    assert entry_point.main([]) == 0
    assert opened == ["menu"]


def test_a_command_goes_to_the_cli_not_the_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(toml_config_reader, "init_version", _initialised)
    dispatched: list[list[str]] = []

    def _cli_main(argv: list[str]) -> int:
        dispatched.append(argv)
        return 0

    monkeypatch.setattr(entry_point, "cli_main", _cli_main)
    monkeypatch.setattr(entry_point, "tui_main", lambda: pytest.fail("the menu was opened"))
    assert entry_point.main(["jobs"]) == 0
    assert dispatched == [["jobs"]]
