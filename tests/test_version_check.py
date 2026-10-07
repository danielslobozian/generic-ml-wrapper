# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the CheckForUpdate use case (a cached, rate-limited PyPI version check)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from generic_ml_wrapper.application.port.outbound.version_check import VersionCheckPort
from generic_ml_wrapper.application.usecase.check_for_update import CheckForUpdateUseCase

_NOW = datetime(2026, 7, 30, 12, 0, 0)


class _Checker(VersionCheckPort):
    def __init__(self, latest: str | None) -> None:
        self.latest = latest
        self.calls = 0

    def latest_version(self, package: str) -> str | None:
        self.calls += 1
        return self.latest


def _use_case(
    tmp_path: Path,
    *,
    checker: VersionCheckPort,
    current_version: str = "1.0.0",
    enabled: bool = True,
    now: datetime = _NOW,
) -> CheckForUpdateUseCase:
    return CheckForUpdateUseCase(
        checker=checker,
        current_version=current_version,
        package="generic-ml-wrapper",
        enabled=lambda: enabled,
        clock=lambda: now,
        cache_path=tmp_path / "update-check.json",
    )


def test_off_never_touches_the_checker_or_cache(tmp_path: Path) -> None:
    checker = _Checker("2.0.0")
    result = _use_case(tmp_path, checker=checker, enabled=False).execute()
    assert result is None
    assert checker.calls == 0
    assert not (tmp_path / "update-check.json").exists()


def test_missing_cache_calls_the_checker_and_writes_a_fresh_cache(tmp_path: Path) -> None:
    checker = _Checker("2.0.0")
    cache_path = tmp_path / "update-check.json"
    result = _use_case(tmp_path, checker=checker).execute()
    assert result == "2.0.0"
    assert checker.calls == 1
    written = json.loads(cache_path.read_text(encoding="utf-8"))
    assert written == {"checked_at": _NOW.isoformat(), "latest": "2.0.0"}


def test_fresh_cache_is_reused_without_calling_the_checker(tmp_path: Path) -> None:
    cache_path = tmp_path / "update-check.json"
    cache_path.write_text(
        json.dumps({"checked_at": (_NOW - timedelta(hours=1)).isoformat(), "latest": "2.0.0"}),
        encoding="utf-8",
    )
    checker = _Checker("3.0.0")  # would be the "real" answer if the port were called
    result = _use_case(tmp_path, checker=checker).execute()
    assert result == "2.0.0"
    assert checker.calls == 0


def test_stale_cache_calls_the_checker_again(tmp_path: Path) -> None:
    cache_path = tmp_path / "update-check.json"
    cache_path.write_text(
        json.dumps({"checked_at": (_NOW - timedelta(hours=25)).isoformat(), "latest": "2.0.0"}),
        encoding="utf-8",
    )
    checker = _Checker("2.1.0")
    result = _use_case(tmp_path, checker=checker).execute()
    assert result == "2.1.0"
    assert checker.calls == 1


def test_checker_failure_produces_no_notice_and_no_cache_write(tmp_path: Path) -> None:
    cache_path = tmp_path / "update-check.json"
    checker = _Checker(None)
    result = _use_case(tmp_path, checker=checker).execute()
    assert result is None
    assert not cache_path.exists()


def test_equal_version_is_not_an_update(tmp_path: Path) -> None:
    checker = _Checker("1.0.0")
    result = _use_case(tmp_path, checker=checker, current_version="1.0.0").execute()
    assert result is None


def test_older_version_is_not_an_update(tmp_path: Path) -> None:
    checker = _Checker("0.9.0")
    result = _use_case(tmp_path, checker=checker, current_version="1.0.0").execute()
    assert result is None


def test_unparseable_cached_version_is_treated_as_not_newer(tmp_path: Path) -> None:
    checker = _Checker("not-a-version")
    result = _use_case(tmp_path, checker=checker).execute()
    assert result is None


def test_malformed_cache_file_is_ignored_like_a_missing_one(tmp_path: Path) -> None:
    cache_path = tmp_path / "update-check.json"
    cache_path.write_text("not json", encoding="utf-8")
    checker = _Checker("2.0.0")
    result = _use_case(tmp_path, checker=checker).execute()
    assert result == "2.0.0"
    assert checker.calls == 1
