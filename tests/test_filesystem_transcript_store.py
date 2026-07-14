# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem transcript store (the per-call in/out/usage trio)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.store.filesystem_transcript_store import (
    FilesystemTranscriptStore,
)
from generic_ml_wrapper.application.domain.model.turn_usage import TurnUsage
from generic_ml_wrapper.application.port.outbound.transcript import TranscriptCall

if TYPE_CHECKING:
    from pathlib import Path


def test_writes_the_self_contained_trio(tmp_path: Path) -> None:
    store = FilesystemTranscriptStore(tmp_path)
    usage = TurnUsage(
        "JOB-1_001", 10, 20, 0.01, "Opus 4.8", timestamp=1.0, duration_s=0.5, turn_id="t1"
    )
    store.record(
        TranscriptCall("JOB-1", "JOB-1_001", 1, b'{"prompt":"hi"}', b"data: chunk\n\n", usage)
    )

    directory = tmp_path / "JOB-1" / "JOB-1_001"
    assert (directory / "call_001.in.json").read_bytes() == b'{"prompt":"hi"}'
    assert (directory / "call_001.out.sse").read_bytes() == b"data: chunk\n\n"
    recorded = json.loads((directory / "call_001.usage.json").read_text(encoding="utf-8"))
    assert recorded["input_tokens"] == 10
    assert recorded["cost_usd"] == 0.01
    assert recorded["model"] == "Opus 4.8"
    assert recorded["turn_id"] == "t1"


def test_no_usage_writes_an_empty_usage_file(tmp_path: Path) -> None:
    store = FilesystemTranscriptStore(tmp_path)
    store.record(TranscriptCall("JOB-1", "JOB-1_001", 2, b"req", b"resp", None))
    usage_file = tmp_path / "JOB-1" / "JOB-1_001" / "call_002.usage.json"
    assert json.loads(usage_file.read_text(encoding="utf-8")) == {}
