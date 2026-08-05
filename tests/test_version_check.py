# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the CheckForUpdateUseCase use case (a cached, rate-limited PyPI version check).

The cache is a fake here, not a file. What this use case decides is *whether the cached
answer is still good enough to skip the network*, and that decision is visible entirely in
which collaborator it asks. How the answer is stored is the adapter's, and is tested
against a real file in ``test_filesystem_update_cache``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from generic_ml_wrapper.application.domain.model.update_check import UpdateCheck
from generic_ml_wrapper.application.port.outbound.update_cache import UpdateCachePort
from generic_ml_wrapper.application.port.outbound.version_check import VersionCheckPort
from generic_ml_wrapper.application.usecase.check_for_update import CheckForUpdateService

_NOW = datetime(2026, 7, 30, 12, 0, 0)


class _Checker(VersionCheckPort):
    def __init__(self, latest: str | None) -> None:
        self.latest = latest
        self.calls = 0

    def latest_version(self, package: str) -> str | None:
        self.calls += 1
        return self.latest


class _Cache(UpdateCachePort):
    def __init__(self, cached: UpdateCheck | None = None) -> None:
        self.cached = cached
        self.reads = 0
        self.recorded: list[UpdateCheck] = []

    def last_check(self) -> UpdateCheck | None:
        self.reads += 1
        return self.cached

    def record(self, check: UpdateCheck) -> None:
        self.recorded.append(check)


def _use_case(
    *,
    checker: VersionCheckPort,
    cache: UpdateCachePort,
    current_version: str = "1.0.0",
    enabled: bool = True,
    now: datetime = _NOW,
) -> CheckForUpdateService:
    return CheckForUpdateService(
        checker=checker,
        current_version=current_version,
        package="generic-ml-wrapper",
        enabled=lambda: enabled,
        clock=lambda: now,
        cache=cache,
    )


def test_off_never_touches_the_checker_or_cache() -> None:
    checker, cache = _Checker("2.0.0"), _Cache()
    result = _use_case(checker=checker, cache=cache, enabled=False).execute()
    assert result is None
    assert checker.calls == 0
    assert cache.reads == 0
    assert cache.recorded == []


def test_missing_cache_calls_the_checker_and_records_the_answer() -> None:
    checker, cache = _Checker("2.0.0"), _Cache()
    result = _use_case(checker=checker, cache=cache).execute()
    assert result == "2.0.0"
    assert checker.calls == 1
    assert cache.recorded == [UpdateCheck(_NOW, "2.0.0")]


def test_fresh_cache_is_reused_without_calling_the_checker() -> None:
    cache = _Cache(UpdateCheck(_NOW - timedelta(hours=1), "2.0.0"))
    checker = _Checker("3.0.0")  # would be the "real" answer if the port were called
    result = _use_case(checker=checker, cache=cache).execute()
    assert result == "2.0.0"
    assert checker.calls == 0
    assert cache.recorded == []


def test_stale_cache_calls_the_checker_again() -> None:
    cache = _Cache(UpdateCheck(_NOW - timedelta(hours=25), "2.0.0"))
    checker = _Checker("2.1.0")
    result = _use_case(checker=checker, cache=cache).execute()
    assert result == "2.1.0"
    assert checker.calls == 1
    assert cache.recorded == [UpdateCheck(_NOW, "2.1.0")]


def test_checker_failure_produces_no_notice_and_records_nothing() -> None:
    checker, cache = _Checker(None), _Cache()
    result = _use_case(checker=checker, cache=cache).execute()
    assert result is None
    assert cache.recorded == []


def test_equal_version_is_not_an_update() -> None:
    checker = _Checker("1.0.0")
    result = _use_case(checker=checker, cache=_Cache(), current_version="1.0.0").execute()
    assert result is None


def test_older_version_is_not_an_update() -> None:
    checker = _Checker("0.9.0")
    result = _use_case(checker=checker, cache=_Cache(), current_version="1.0.0").execute()
    assert result is None


def test_unparseable_version_is_treated_as_not_newer() -> None:
    checker = _Checker("not-a-version")
    result = _use_case(checker=checker, cache=_Cache()).execute()
    assert result is None
