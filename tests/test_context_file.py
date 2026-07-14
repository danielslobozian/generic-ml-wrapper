# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the durable per-session context file writer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.caller import context_file
from generic_ml_wrapper.common import paths

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_write_persists_context_per_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths, "CONTEXTS", tmp_path)
    path = context_file.write("JOB-1", "JOB-1_001", "MY CONTEXT")
    assert path == tmp_path / "JOB-1" / "JOB-1_001.context.md"
    assert path.read_text(encoding="utf-8") == "MY CONTEXT"
    assert path.exists()  # durable: it survives the run, unlike the old temp file


def test_write_overwrites_same_session_and_isolates_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(paths, "CONTEXTS", tmp_path)
    context_file.write("JOB-1", "JOB-1_001", "first")
    same = context_file.write("JOB-1", "JOB-1_001", "second")  # re-launch overwrites
    assert same.read_text(encoding="utf-8") == "second"
    other = context_file.write("JOB-1", "JOB-1_002", "other")
    assert other.read_text(encoding="utf-8") == "other"
