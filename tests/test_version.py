# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for `gmlw --version`."""

import pytest

from generic_ml_wrapper import __version__
from generic_ml_wrapper.adapter.inbound.cli import app


def test_version_string_names_the_tool_and_version() -> None:
    assert app._version_string().startswith(f"gmlw {__version__} ")


def test_version_string_is_a_single_line() -> None:
    # The status-line and help surfaces stay single-line; --version does too.
    assert "\n" not in app._version_string()


def test_version_flag_prints_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        app.main(["--version"])
    assert exit_info.value.code == 0
    assert f"gmlw {__version__}" in capsys.readouterr().out
