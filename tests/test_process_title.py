# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for naming the gmlw process, and for the CLI doing it only as the console script."""

from collections.abc import Callable

import pytest

from generic_ml_wrapper.adapter.inbound.cli import app, process_title


def test_the_process_is_renamed_gmlw(monkeypatch: pytest.MonkeyPatch) -> None:
    names: list[str] = []
    monkeypatch.setattr(process_title, "setproctitle", names.append)

    restore = process_title.name_the_process()

    assert names == ["gmlw"]
    restore()  # never raises, whatever the platform had to undo


def _record_naming(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the CLI's process naming with a recorder of what was named and restored."""
    events: list[str] = []

    def name() -> Callable[[], None]:
        events.append("named")
        return lambda: events.append("restored")

    def succeed(_argv: list[str]) -> int:
        return 0

    monkeypatch.setattr(app, "name_the_process", name)
    monkeypatch.setattr(app, "_dispatch", succeed)
    return events


def test_the_console_script_names_the_process_and_restores_on_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _record_naming(monkeypatch)
    monkeypatch.setattr("sys.argv", ["gmlw"])

    assert app.main() == 0
    assert events == ["named", "restored"]


def test_the_title_is_restored_even_when_the_run_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    events = _record_naming(monkeypatch)
    monkeypatch.setattr("sys.argv", ["gmlw"])

    def boom(_argv: list[str]) -> int:
        raise ValueError("kaboom")

    monkeypatch.setattr(app, "_dispatch", boom)

    assert app.main() == 1
    assert events == ["named", "restored"]


def test_a_caller_passing_its_own_arguments_keeps_its_process_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _record_naming(monkeypatch)

    assert app.main([]) == 0
    assert events == []
