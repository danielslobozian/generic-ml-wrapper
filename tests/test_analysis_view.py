# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for rendering a session analysis, and the ``gmlw analyze`` command."""

import json
from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.inbound.cli import app
from generic_ml_wrapper.adapter.inbound.cli.analysis_view import format_analysis, format_duration
from generic_ml_wrapper.application.domain.model.session_analysis import (
    RecordedCall,
    RecordedPrompt,
    RecordedToolCall,
    SessionAnalysis,
    SessionRecord,
)
from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts
from generic_ml_wrapper.application.domain.service.session_analyzer import analyze
from generic_ml_wrapper.application.port.inbound.analyze_session import (
    AnalyzeSession,
    NothingToAnalyzeError,
)
from generic_ml_wrapper.common import i18n


@pytest.mark.parametrize(
    ("seconds", "shown"),
    [(0.04, "0s"), (0.42, "0.4s"), (3.0, "3s"), (12.4, "12s"), (61.0, "1m"), (3900.0, "1h05m")],
)
def test_durations_keep_a_tenth_only_while_it_says_something(seconds: float, shown: str) -> None:
    assert format_duration(seconds) == shown


def _analysis(session_id: str | None = "j_001") -> SessionAnalysis:
    record = SessionRecord(
        "claude",
        str(Path.home() / ".claude" / "projects" / "p" / "s.jsonl"),
        1792836000.0,
        1792839600.0,
        calls=(
            RecordedCall(TokenCounts(1500, 2000, 3_000_000, 4000), model="opus"),
            RecordedCall(TokenCounts(), by_agent=True),
        ),
        prompts=(RecordedPrompt(0.0, 30.0), RecordedPrompt(100.0, 190.0)),
        tool_calls=(RecordedToolCall("Bash", 0.0, 0.5), RecordedToolCall("Bash", 1.0, 2.0)),
    )
    return analyze(record, session_id)


def test_an_analysis_shows_each_figure_on_its_own_line() -> None:
    text = format_analysis(_analysis(), i18n.load_localizer("en"))

    assert text.splitlines()[0] == "Session j_001 · claude"
    assert "~/.claude/projects/p/s.jsonl" in text
    assert "(1h)" in text
    assert "turns       2 (main 1 · agents 1)    prompts 2" in text
    assert "↑ 1.5k  ↓ 2k  ⟲ 3M  ✎ 4k" in text
    assert "min 30s · median 1m · avg 1m · max 1m" in text
    assert "⚒ 2 (Bash 2)" in text
    assert "Bash: median 0.8s · max 1s  (2 returned)" in text
    assert "approval" in text


def test_a_session_outside_gmlw_with_nothing_in_it_says_so() -> None:
    empty = analyze(SessionRecord("codex", "/tmp/r.jsonl", None, None))

    text = format_analysis(empty, i18n.load_localizer("en"))

    assert text.splitlines()[0] == "Session outside gmlw · codex"
    assert "none finished" in text
    assert "tools       none" in text
    assert "models      unknown" in text


class _Fixed(AnalyzeSession):
    def __init__(self, result: tuple[SessionAnalysis, ...] | None) -> None:
        self._result = result

    def execute(self, target: str) -> tuple[SessionAnalysis, ...]:
        if self._result is None:
            raise NothingToAnalyzeError("analyze.error.nothing", target=target)
        return self._result


def test_the_command_prints_json_for_other_tools(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_analyze_session", lambda: _Fixed((_analysis(),)))

    assert app.main(["analyze", "j_001", "--json"]) == 0

    (payload,) = json.loads(capsys.readouterr().out)
    assert payload["session_id"] == "j_001"
    assert payload["tokens"]["cache_read"] == 3_000_000


def test_the_command_explains_what_it_cannot_analyse(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(app, "build_analyze_session", lambda: _Fixed(None))

    assert app.main(["analyze", "nope"]) == 2

    assert "'nope'" in capsys.readouterr().err
