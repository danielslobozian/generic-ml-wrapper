# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the SessionLogger reference hook."""

from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.hook.session_logger import SessionLogger
from generic_ml_wrapper.application.domain.service.hook import HookContext, HookPhase


def _context(
    phase: HookPhase, exit_code: int | None, cwd: str | None = "/work/acme"
) -> HookContext:
    return HookContext(
        phase=phase,
        job="JOB-1",
        session_id="JOB-1_001",
        client="claude",
        uuid=None,
        resume=False,
        cwd=cwd,
        exit_code=exit_code,
    )


def test_appends_a_line_per_seam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("generic_ml_wrapper.common.paths.HOME", tmp_path)
    logger = SessionLogger()
    logger.run(_context(HookPhase.PRE_LAUNCH, exit_code=None))
    logger.run(_context(HookPhase.POST_SESSION, exit_code=0))

    lines = (tmp_path / "sessions.log").read_text(encoding="utf-8").splitlines()
    assert lines == [
        "-> start JOB-1/JOB-1_001 on claude in /work/acme",
        "<- end   JOB-1/JOB-1_001 on claude exit 0",
    ]


def test_post_session_records_an_unknown_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("generic_ml_wrapper.common.paths.HOME", tmp_path)
    SessionLogger().run(_context(HookPhase.POST_SESSION, exit_code=None))
    log = (tmp_path / "sessions.log").read_text(encoding="utf-8")
    assert log == "<- end   JOB-1/JOB-1_001 on claude exit ?\n"


def test_creates_the_home_directory_if_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "not-there-yet"
    monkeypatch.setattr("generic_ml_wrapper.common.paths.HOME", home)
    SessionLogger().run(_context(HookPhase.PRE_LAUNCH, exit_code=None))
    assert (home / "sessions.log").is_file()


def test_a_write_failure_is_swallowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # HOME points at a *file*, so mkdir/open fail; the hook must not raise (best-effort).
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setattr("generic_ml_wrapper.common.paths.HOME", blocker / "under-a-file")
    SessionLogger().run(_context(HookPhase.PRE_LAUNCH, exit_code=None))  # does not raise
