# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the process-wide diagnostics handle (``common.log``)."""

from collections.abc import Iterator

import pytest

from generic_ml_wrapper.adapter.outbound.diagnostics.stderr_diagnostics import StderrDiagnostics
from generic_ml_wrapper.application.domain.service.diagnostics import Diagnostics
from generic_ml_wrapper.application.wiring.diagnostics_log import Log, active, set_active


@pytest.fixture(autouse=True)
def _restore_sink() -> Iterator[None]:
    previous = set_active(StderrDiagnostics(level="warning"))
    yield
    set_active(previous)


class _Recorder(Diagnostics):
    """A sink that keeps what it was handed, for asserting on the call, not the format."""

    def __init__(self) -> None:
        self.records: list[tuple[str, str, BaseException | None, dict[str, object]]] = []

    def debug(self, message: str, **context: object) -> None:
        self.records.append(("debug", message, None, context))

    def info(self, message: str, **context: object) -> None:
        self.records.append(("info", message, None, context))

    def warning(self, message: str, **context: object) -> None:
        self.records.append(("warning", message, None, context))

    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None:
        self.records.append(("error", message, exc, context))


def test_messages_below_threshold_are_dropped(capsys: pytest.CaptureFixture[str]) -> None:
    Log().info("quiet")  # info < warning (the default) -> dropped
    Log().warning("loud")
    err = capsys.readouterr().err
    assert "quiet" not in err
    assert "gmlw WARNING loud" in err


def test_a_lower_threshold_lets_debug_through(capsys: pytest.CaptureFixture[str]) -> None:
    set_active(StderrDiagnostics(level="debug"))
    Log().debug("now visible")
    assert "gmlw DEBUG now visible" in capsys.readouterr().err


def test_bound_context_is_rendered(capsys: pytest.CaptureFixture[str]) -> None:
    Log().bind("JOB-1", "JOB-1_001").error("boom")
    assert "gmlw ERROR [JOB-1] [JOB-1_001] boom" in capsys.readouterr().err


def test_empty_labels_are_ignored() -> None:
    assert Log().bind("JOB-1", "", "JOB-1_001").context == ("JOB-1", "JOB-1_001")


def test_the_default_sink_is_silent(capsys: pytest.CaptureFixture[str]) -> None:
    # Nothing may be written before the composition root installs a sink: the domain
    # imports this module, so it can hold no adapter to fall back on.
    from generic_ml_wrapper.application.wiring.diagnostics_log import (  # noqa: PLC0415
        _NoDiagnostics,
    )

    set_active(_NoDiagnostics())
    Log().error("into the void")
    assert capsys.readouterr().err == ""


def test_records_reach_the_active_sink_with_their_context() -> None:
    recorder = _Recorder()
    set_active(recorder)
    Log().bind("JOB-1").warning("upstream failed", client="claude")
    level, message, exc, context = recorder.records[0]
    assert (level, message, exc) == ("warning", "[JOB-1] upstream failed", None)
    assert context == {"client": "claude"}


def test_an_exception_is_passed_through_for_the_sink_to_render() -> None:
    recorder = _Recorder()
    set_active(recorder)
    boom = ValueError("nope")
    Log().error("it broke", exc=boom, key="log.broke")
    _, _, exc, context = recorder.records[0]
    assert exc is boom
    assert context == {"key": "log.broke"}


def test_set_active_returns_the_previous_sink() -> None:
    first = _Recorder()
    set_active(first)
    second = _Recorder()
    assert set_active(second) is first
    assert active() is second
