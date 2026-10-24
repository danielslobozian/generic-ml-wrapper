# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for finding and reading Claude Code's and Codex's own session files."""

import json
from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.session_file.client_session_files import (
    ClientSessionFiles,
)
from generic_ml_wrapper.application.domain.model.session_analysis import (
    RecordedPrompt,
    RecordedToolCall,
)
from generic_ml_wrapper.application.domain.model.token_counts import TokenCounts

_CONTENT = "the user's words, never to be read"


def _at(second: int) -> str:
    return f"2026-10-24T10:00:{second:02d}.000Z"


def _epoch(second: int) -> float:
    return 1792836000.0 + second


def _write(path: Path, records: list[dict[str, object]], *, tail: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in records) + tail, encoding="utf-8")
    return path


def _usage(base: int) -> dict[str, int]:
    return {
        "input_tokens": base,
        "output_tokens": base * 2,
        "cache_read_input_tokens": base * 3,
        "cache_creation_input_tokens": base * 4,
    }


def _user(second: int, **fields: object) -> dict[str, object]:
    return {"type": "user", "timestamp": _at(second), **fields}


def _answer(second: int, message_id: str, model: str, **message: object) -> dict[str, object]:
    return {
        "type": "assistant",
        "timestamp": _at(second),
        "message": {"id": message_id, "model": model, **message},
    }


def _claude_session(projects: Path) -> Path:
    """A Claude Code session: two prompts, one tool call, an answer in two blocks, an agent."""
    human = {"origin": {"kind": "human"}, "message": {"content": _CONTENT}}
    main = _write(
        projects / "-home-u-proj" / "s-1.jsonl",
        [
            {"type": "custom-title", "sessionId": "s-1"},  # bookkeeping: no timestamp
            _user(0, sessionId="s-1", **human),
            _answer(
                2,
                "m-1",
                "claude-opus-5-5",
                usage=_usage(1),
                content=[{"type": "text", "text": _CONTENT}],
            ),
            # The same answer's second block repeats its usage: counted once.
            _answer(
                3,
                "m-1",
                "claude-opus-5-5",
                usage=_usage(1),
                content=[{"type": "tool_use", "id": "t-1", "name": "Bash"}],
            ),
            _user(5, message={"content": [{"type": "tool_result", "tool_use_id": "t-1"}]}),
            # An agent reporting back: not a prompt.
            _user(6, origin={"kind": "task-notification"}, message={"content": _CONTENT}),
            _answer(9, "m-2", "<synthetic>", usage=_usage(10)),
            _user(20, **human),
        ],
        tail='{"type": "assistant", "timest',  # a line still being written
    )
    agent = _answer(7, "m-3", "claude-haiku-5-5", usage=_usage(100))
    _write(
        projects / "-home-u-proj" / "s-1" / "subagents" / "agent-a.jsonl",
        [{**agent, "isSidechain": True}],
    )
    return main


def test_a_claude_session_is_read_from_its_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    main = _claude_session(tmp_path / "projects")
    files = ClientSessionFiles()

    source = files.locate("claude", "s-1")
    assert source == str(main)
    record = files.read(str(main))

    assert record is not None
    assert record.client == "claude"
    assert (record.started_at, record.ended_at) == (_epoch(0), _epoch(20))
    assert [(c.tokens, c.by_agent, c.model) for c in record.calls] == [
        (TokenCounts(1, 2, 3, 4), False, "claude-opus-5-5"),
        (TokenCounts(10, 20, 30, 40), False, None),  # made up by the client: no model
        (TokenCounts(100, 200, 300, 400), True, "claude-haiku-5-5"),
    ]
    # The first prompt is answered by the last record before the second; the second, by nothing.
    assert record.prompts == (RecordedPrompt(_epoch(0), _epoch(9)), RecordedPrompt(_epoch(20)))
    assert record.tool_calls == (RecordedToolCall("Bash", _epoch(3), _epoch(5)),)


def test_an_older_claude_file_without_origin_tells_prompts_from_tool_results(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path / "old.jsonl",
        [
            {"type": "user", "sessionId": "o", "timestamp": _at(0), "message": {"content": "x"}},
            {"type": "user", "timestamp": _at(1), "isMeta": True, "message": {"content": "x"}},
            {
                "type": "user",
                "timestamp": _at(2),
                "message": {"content": [{"type": "tool_result", "tool_use_id": "t"}]},
            },
        ],
    )

    record = ClientSessionFiles().read(str(path))

    assert record is not None
    assert record.prompts == (RecordedPrompt(_epoch(0), _epoch(2)),)


def _line(kind: str, second: int, **payload: object) -> dict[str, object]:
    return {"type": kind, "timestamp": _at(second), "payload": payload}


def _usage_record(
    second: int, thread: str, fresh_and_cached: int, cached: int, output: int
) -> dict[str, object]:
    usage = {
        "input_tokens": fresh_and_cached,
        "cached_input_tokens": cached,
        "output_tokens": output,
    }
    return _line("token_usage_record", second, thread_id=thread, usage=usage)


def _codex_rollout(sessions: Path) -> Path:
    """A Codex rollout: one prompt answered, one task codex started itself, an agent request."""
    by_user = {"turn_trigger": "user"}
    return _write(
        sessions / "2026" / "10" / "24" / "rollout-2026-10-24T10-00-00-c-1.jsonl",
        [
            _line("session_meta", 0, id="c-1"),
            _line("turn_context", 1, model="gpt-6"),
            _line("event_msg", 1, type="task_started", turn_id="u-1", turn_attribution=by_user),
            _line("event_msg", 2, type="task_started", turn_id="x-1", turn_attribution={}),
            _usage_record(3, "c-1", 100, 80, 5),
            _usage_record(4, "agent-thread", 10, 0, 1),
            _line("response_item", 5, type="custom_tool_call", name="exec", call_id="k-1"),
            _line(
                "response_item", 7, type="custom_tool_call_output", call_id="k-1", output=_CONTENT
            ),
            _line("response_item", 8, type="function_call", name="spawn_agent", call_id="k-2"),
            _line("event_msg", 12, type="turn_aborted", turn_id="u-1"),
        ],
    )


def test_a_codex_rollout_is_read_from_its_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    rollout = _codex_rollout(tmp_path / "sessions")
    files = ClientSessionFiles()

    source = files.locate("codex", "c-1")
    assert source == str(rollout)
    record = files.read(str(rollout))

    assert record is not None
    assert record.client == "codex"
    assert [(c.tokens, c.by_agent, c.model) for c in record.calls] == [
        (TokenCounts(20, 5, 80, 0), False, "gpt-6"),  # input counts the cache: 100 - 80 fresh
        (TokenCounts(10, 1, 0, 0), True, "gpt-6"),
    ]
    assert record.prompts == (RecordedPrompt(_epoch(1), _epoch(12)),)  # codex's own task left out
    assert record.tool_calls == (
        RecordedToolCall("exec", _epoch(5), _epoch(7)),
        RecordedToolCall("spawn_agent", _epoch(8)),
    )


def test_unknown_clients_and_missing_sessions_locate_nothing(tmp_path: Path) -> None:
    files = ClientSessionFiles()

    assert files.locate("cursor", "x") is None
    assert files.locate("claude", "no-such-session") is None
    assert files.analyzable_clients() == {"claude", "codex"}


def test_a_file_no_client_wrote_or_no_file_at_all_reads_as_nothing(tmp_path: Path) -> None:
    files = ClientSessionFiles()
    stranger = _write(tmp_path / "other.jsonl", [{"type": "something"}] * 30)

    assert files.read(str(stranger)) is None
    assert files.read(str(tmp_path / "missing.jsonl")) is None
    assert files.read(str(tmp_path)) is None
