# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for turning a session's recorded metadata into its figures."""

from generic_ml_wrapper.application.domain.model.session_analysis import (
    DurationStats,
    RecordedCall,
    RecordedPrompt,
    RecordedToolCall,
    SessionRecord,
)
from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts
from generic_ml_wrapper.application.domain.service.session_analyzer import analyze


def test_no_durations_have_no_spread() -> None:
    assert DurationStats.of([]) is None


def test_the_spread_of_an_even_count_takes_the_middle_pair_for_its_median() -> None:
    assert DurationStats.of([4.0, 1.0, 3.0, 2.0]) == DurationStats(
        count=4, minimum=1.0, median=2.5, mean=2.5, maximum=4.0
    )


def _record(
    *,
    calls: tuple[RecordedCall, ...] = (),
    prompts: tuple[RecordedPrompt, ...] = (),
    tool_calls: tuple[RecordedToolCall, ...] = (),
    started_at: float | None = 100.0,
    ended_at: float | None = 400.0,
) -> SessionRecord:
    return SessionRecord("claude", "/s.jsonl", started_at, ended_at, calls, prompts, tool_calls)


def test_requests_are_totalled_and_split_between_main_and_agents() -> None:
    record = _record(
        calls=(
            RecordedCall(TokenCounts(1, 2, 3, 4), model="opus"),
            RecordedCall(TokenCounts(10, 20, 30, 40), by_agent=True, model="haiku"),
            RecordedCall(TokenCounts(100, 200, 300, 400), model="opus"),
        )
    )

    analysis = analyze(record, "J_001")

    assert analysis.session_id == "J_001"
    assert (analysis.main_turns, analysis.agent_turns) == (2, 1)
    assert analysis.tokens == TokenCounts(111, 222, 333, 444)
    assert analysis.models == ("opus", "haiku")  # most used first


def test_only_answered_prompts_are_timed_but_every_prompt_counts() -> None:
    record = _record(
        prompts=(RecordedPrompt(100.0, 110.0), RecordedPrompt(200.0, 230.0), RecordedPrompt(300.0))
    )

    analysis = analyze(record)

    assert analysis.prompts == 3
    assert analysis.answer_times == DurationStats(2, 10.0, 20.0, 20.0, 30.0)


def test_tools_are_counted_by_name_and_timed_when_they_returned() -> None:
    record = _record(
        tool_calls=(
            RecordedToolCall("Bash", 100.0, 101.0),
            RecordedToolCall("Read", 102.0, 102.5),
            RecordedToolCall("Bash", 103.0, 106.0),
            RecordedToolCall("Bash", 107.0),  # never returned: counted, not timed
            RecordedToolCall("Edit", 108.0),
        )
    )

    analysis = analyze(record)

    assert analysis.tools.counts == (("Bash", 3), ("Edit", 1), ("Read", 1))
    assert [(t.name, t.durations.count, t.durations.maximum) for t in analysis.tool_times] == [
        ("Bash", 2, 3.0),
        ("Read", 1, 0.5),
    ]


def test_an_empty_record_has_nothing_to_show() -> None:
    analysis = analyze(_record(started_at=None, ended_at=None))

    assert analysis.models == ()
    assert analysis.answer_times is None
    assert analysis.tools.total == 0
    assert analysis.tool_times == ()
