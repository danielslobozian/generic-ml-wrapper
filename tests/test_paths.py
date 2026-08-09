# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The root every wrapper location is derived from."""

from __future__ import annotations

from pathlib import Path

import pytest

from generic_ml_wrapper.application.wiring.paths import HOME_VARIABLE, Paths


def test_the_root_defaults_to_a_dot_folder_in_the_users_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(HOME_VARIABLE, raising=False)
    assert Paths().home == Path.home() / ".gmlw"


def test_the_variable_names_the_root_itself_rather_than_its_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A dev tree is pointed at wholesale: nothing is appended, so the variable cannot
    # land the tree at <root>/.gmlw and quietly share the real one's neighbourhood.
    monkeypatch.setenv(HOME_VARIABLE, str(tmp_path / "gmlw-dev"))
    assert Paths().home == tmp_path / "gmlw-dev"


def test_every_location_moves_with_the_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(HOME_VARIABLE, str(tmp_path / "gmlw-dev"))
    paths = Paths()
    assert paths.ledger == tmp_path / "gmlw-dev" / "ledger.db"
    assert paths.log_file == tmp_path / "gmlw-dev" / "logs" / "gmlw.log"
    assert paths.config_file == tmp_path / "gmlw-dev" / "config.toml"


def test_a_blank_variable_is_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    # An exported-but-empty variable is a shell accident, not a request to root the
    # tree at the current directory.
    monkeypatch.setenv(HOME_VARIABLE, "   ")
    assert Paths().home == Path.home() / ".gmlw"


def test_a_tilde_in_the_variable_is_expanded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(HOME_VARIABLE, "~/.gmlw-dev")
    assert Paths().home == Path.home() / ".gmlw-dev"
