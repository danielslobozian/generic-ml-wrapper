# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem ``UpdateCachePort``: the file, and what unreadable means."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.i18n.json_catalog_localizer import (
    JsonCatalogLocalizerFactory,
)
from generic_ml_wrapper.adapter.outbound.update.filesystem_update_cache import (
    FilesystemUpdateCacheAdapter,
)
from generic_ml_wrapper.application.domain.model.update_check import UpdateCheck
from generic_ml_wrapper.application.port.outbound.diagnostics import DiagnosticsPort

if TYPE_CHECKING:
    from pathlib import Path

_WHEN = datetime(2026, 7, 30, 12, 0, 0)


class _RecordingDiagnostics(DiagnosticsPort):
    def __init__(self) -> None:
        self.keys: list[str] = []

    def debug(self, message: str, **context: object) -> None:
        self.keys.append(str(context.get("key", "")))

    def info(self, message: str, **context: object) -> None:
        self.keys.append(str(context.get("key", "")))

    def warning(self, message: str, **context: object) -> None:
        self.keys.append(str(context.get("key", "")))

    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None:
        self.keys.append(str(context.get("key", "")))


def _cache(
    cache_file: Path, diagnostics: DiagnosticsPort | None = None
) -> FilesystemUpdateCacheAdapter:
    return FilesystemUpdateCacheAdapter(
        cache_file,
        diagnostics or _RecordingDiagnostics(),
        JsonCatalogLocalizerFactory().load("en"),
    )


def test_records_a_check_and_reads_it_back(tmp_path: Path) -> None:
    cache = _cache(tmp_path / "state" / "update-check.json")  # folder does not exist yet
    cache.record(UpdateCheck(_WHEN, "2.0.0"))
    assert cache.last_check() == UpdateCheck(_WHEN, "2.0.0")


def test_records_the_check_in_the_documented_shape(tmp_path: Path) -> None:
    cache_file = tmp_path / "update-check.json"
    _cache(cache_file).record(UpdateCheck(_WHEN, "2.0.0"))
    written = json.loads(cache_file.read_text(encoding="utf-8"))
    assert written == {"checked_at": _WHEN.isoformat(), "latest": "2.0.0"}


def test_a_missing_file_has_no_last_check(tmp_path: Path) -> None:
    assert _cache(tmp_path / "absent.json").last_check() is None


def test_a_malformed_file_reads_like_a_missing_one(tmp_path: Path) -> None:
    cache_file = tmp_path / "update-check.json"
    cache_file.write_text("not json", encoding="utf-8")
    assert _cache(cache_file).last_check() is None


def test_a_file_missing_its_version_reads_like_a_missing_one(tmp_path: Path) -> None:
    cache_file = tmp_path / "update-check.json"
    cache_file.write_text(json.dumps({"checked_at": _WHEN.isoformat()}), encoding="utf-8")
    assert _cache(cache_file).last_check() is None


def test_a_failed_write_is_reported_and_not_raised(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("in the way", encoding="utf-8")  # a file where a folder must go
    diagnostics = _RecordingDiagnostics()
    _cache(blocker / "update-check.json", diagnostics).record(UpdateCheck(_WHEN, "2.0.0"))
    assert diagnostics.keys == ["log.update_cache_not_recorded"]
