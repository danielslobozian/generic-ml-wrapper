# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for HTTP/version reading: pure extractors, probe fallback, offline safety."""

from __future__ import annotations

import pytest

from generic_ml_wrapper.adapter.outbound.bootstrap import http_client_versions as hcv
from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.domain.model.client_catalog import VersionProbe


def test_parse_version_pulls_a_token_out_of_noise() -> None:
    assert hcv.parse_version("Claude Code 2.1.215 (native)") == "2.1.215"
    assert hcv.parse_version("cursor-agent 2026.07.16-899851b") == "2026.07.16-899851b"
    assert hcv.parse_version("no version here") is None
    assert hcv.parse_version(None) is None


def test_extract_reads_each_probe_kind() -> None:
    assert (
        hcv.extract(VersionProbe("json", "u", "info.version"), '{"info":{"version":"2.21.0"}}')
        == "2.21.0"
    )
    assert (
        hcv.extract(VersionProbe("regex", "u", r"lab/([^/]+)/"), "x/lab/2026.07.16-899851b/y")
        == "2026.07.16-899851b"
    )
    assert hcv.extract(VersionProbe("text", "u"), "  2.1.205\n") == "2.1.205"


def test_extract_strips_a_tag_prefix() -> None:
    probe = VersionProbe("json", "u", "tag_name", strip_prefix="rust-v")
    assert hcv.extract(probe, '{"tag_name":"rust-v0.144.6"}') == "0.144.6"


def test_outdated_only_flags_a_strictly_older_install() -> None:
    assert hcv.outdated("2.1.200", "2.1.215") is True
    assert hcv.outdated("2.1.215", "2.1.215") is False
    # A local build ahead of the published channel (Claude stable lags) is not "outdated".
    assert hcv.outdated("2.1.215", "2.1.205") is False
    # Cursor's date-hash format compares on its numeric parts.
    assert hcv.outdated("2026.07.16-899851b", "2026.07.23-abc") is True
    # Uncomparable input never nags.
    assert hcv.outdated("unknown", "2.1.0") is False


def test_installed_parses_the_version_flag_output(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Completed:
        stdout = "2.1.215 (Claude Code)\n"
        stderr = ""

    def _run(*_a: object, **_k: object) -> _Completed:
        return _Completed()

    monkeypatch.setattr(hcv.subprocess, "run", _run)
    assert hcv.HttpClientVersions().installed(client_catalog.CLAUDE) == "2.1.215"


def test_installed_is_none_when_the_client_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing(*_a: object, **_k: object) -> object:
        raise FileNotFoundError

    monkeypatch.setattr(hcv.subprocess, "run", _missing)
    assert hcv.HttpClientVersions().installed(client_catalog.CLAUDE) is None


def test_latest_uses_the_primary_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    versions = hcv.HttpClientVersions()

    def _fetch(_url: str) -> str | None:
        return '{"version":"0.144.6"}'

    monkeypatch.setattr(versions, "_fetch", _fetch)
    assert versions.latest(client_catalog.CODEX) == "0.144.6"


def test_latest_falls_back_when_the_primary_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fetch(url: str) -> str | None:
        if "registry.npmjs" in url:
            return None  # primary channel down
        if "api.github.com" in url:
            return '{"tag_name":"rust-v0.144.6"}'
        return None

    versions = hcv.HttpClientVersions()
    monkeypatch.setattr(versions, "_fetch", _fetch)
    assert versions.latest(client_catalog.CODEX) == "0.144.6"


def test_latest_is_none_when_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    versions = hcv.HttpClientVersions()

    def _fetch(_url: str) -> str | None:
        return None

    monkeypatch.setattr(versions, "_fetch", _fetch)
    assert versions.latest(client_catalog.VIBE) is None
