# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the PATH-backed client detector."""

from collections.abc import Callable

import pytest

from generic_ml_wrapper.adapter.outbound.bootstrap import path_client_detector
from generic_ml_wrapper.adapter.outbound.bootstrap.path_client_detector import PathClientDetector


def _only(*commands: str) -> Callable[[str], str | None]:
    """A ``shutil.which`` stand-in that resolves only the given commands."""
    present = set(commands)

    def which(command: str) -> str | None:
        return f"/usr/bin/{command}" if command in present else None

    return which


def test_reports_nothing_when_no_command_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(path_client_detector.shutil, "which", _only())
    assert PathClientDetector().available() == []


def test_maps_cursor_to_its_cursor_agent_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(path_client_detector.shutil, "which", _only("cursor-agent"))
    assert PathClientDetector().available() == ["cursor"]


def test_returns_installed_clients_in_canonical_order(monkeypatch: pytest.MonkeyPatch) -> None:
    # Report them out of order; the detector still returns claude-first canonical order.
    monkeypatch.setattr(path_client_detector.shutil, "which", _only("vibe", "codex", "claude"))
    assert PathClientDetector().available() == ["claude", "codex", "vibe"]
