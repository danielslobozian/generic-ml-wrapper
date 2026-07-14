# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the diagnostic logging facility."""

import pytest

from generic_ml_wrapper.common.log import Log, configure


@pytest.fixture(autouse=True)
def _reset_threshold() -> None:
    # Isolate each test from the global threshold (reset to the default).
    configure("warning")


def test_messages_below_threshold_are_dropped(capsys: pytest.CaptureFixture[str]) -> None:
    Log().info("quiet")  # info < warning (default) → dropped
    Log().warning("loud")
    err = capsys.readouterr().err
    assert "quiet" not in err
    assert "gmlw WARNING loud" in err


def test_configure_lowers_the_threshold(capsys: pytest.CaptureFixture[str]) -> None:
    assert configure("debug") == "debug"
    Log().debug("now visible")
    assert "gmlw DEBUG now visible" in capsys.readouterr().err


def test_unknown_level_falls_back_to_warning() -> None:
    assert configure("bogus") == "warning"
    assert configure(None) == "warning"


def test_bound_context_is_rendered(capsys: pytest.CaptureFixture[str]) -> None:
    Log().bind("JOB-1", "JOB-1_001").error("boom")
    assert "gmlw ERROR [JOB-1] [JOB-1_001] boom" in capsys.readouterr().err
