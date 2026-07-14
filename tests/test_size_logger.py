# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the reference MessageSizeLogger interceptor."""

import pytest

from generic_ml_wrapper.adapter.outbound.interceptor.size_logger import MessageSizeLogger
from generic_ml_wrapper.common.log import configure


@pytest.fixture(autouse=True)
def _reset_threshold() -> None:
    configure("warning")


def test_returns_the_text_unchanged() -> None:
    assert MessageSizeLogger().intercept("hello", "request") == "hello"


def test_logs_the_target_and_size(capsys: pytest.CaptureFixture[str]) -> None:
    configure("info")
    MessageSizeLogger().intercept("hello", "response")
    err = capsys.readouterr().err
    assert "response" in err
    assert "5 chars" in err
