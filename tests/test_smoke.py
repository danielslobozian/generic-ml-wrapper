# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Smoke test: the package imports and its entry point runs."""

import pytest

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.inbound.cli import app
from generic_ml_wrapper.adapter.inbound.cli.app import main


def test_version_is_a_nonempty_string() -> None:
    assert isinstance(__version__, str)
    assert __version__


def _initialised(*_: object, **__: object) -> str:
    return "0.4.0"  # the gate sees an initialised install


def test_main_with_no_args_prints_the_index_and_exits_zero(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Pin an initialised install so bare gmlw shows the capability index (the "thereafter"
    # path), not the first-run init interview.
    monkeypatch.setattr(app.config, "init_version", _initialised)
    assert main([]) == 0
    assert "gmlw" in capsys.readouterr().out
