# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for where gmlw keeps its own files."""

from __future__ import annotations

from pathlib import Path

import pytest

from generic_ml_wrapper.common.paths import resolve_home


def test_the_home_is_under_the_users_home_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GMLW_HOME", raising=False)
    assert resolve_home() == Path.home() / ".gmlw"


def test_gmlw_home_moves_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GMLW_HOME", str(tmp_path / "dev"))
    assert resolve_home() == tmp_path / "dev"


def test_gmlw_home_expands_a_tilde(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMLW_HOME", "~/.gmlw-dev")
    assert resolve_home() == Path.home() / ".gmlw-dev"


def test_an_empty_gmlw_home_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMLW_HOME", "")
    assert resolve_home() == Path.home() / ".gmlw"
