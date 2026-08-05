# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the reference MessageSizeLoggerAdapter interceptor."""

from collections.abc import Iterator

import pytest

from generic_ml_wrapper.adapter.outbound.diagnostics.stderr_diagnostics import (
    StderrDiagnosticsAdapter,
)
from generic_ml_wrapper.adapter.outbound.interceptor.size_logger import MessageSizeLoggerAdapter
from generic_ml_wrapper.application.wiring.diagnostics_log import set_active


@pytest.fixture(autouse=True)
def _stderr_sink() -> Iterator[None]:
    previous = set_active(StderrDiagnosticsAdapter(level="warning"))
    yield
    set_active(previous)


def test_returns_the_text_unchanged() -> None:
    assert MessageSizeLoggerAdapter().intercept("hello", "request") == "hello"


def test_logs_the_target_and_size(capsys: pytest.CaptureFixture[str]) -> None:
    set_active(StderrDiagnosticsAdapter(level="info"))
    MessageSizeLoggerAdapter().intercept("hello", "response")
    err = capsys.readouterr().err
    assert "response" in err
    assert "5 chars" in err
