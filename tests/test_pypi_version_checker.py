# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for PypiVersionCheckerAdapter: PyPI JSON API reads, every failure degrading to None."""

from __future__ import annotations

import json
import urllib.error
from email.message import Message
from typing import Any

import pytest

from generic_ml_wrapper.adapter.outbound.update import pypi_version_checker as checker_module
from generic_ml_wrapper.adapter.outbound.update.pypi_version_checker import (
    PypiVersionCheckerAdapter,
)


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        pass


def _stub_urlopen(monkeypatch: pytest.MonkeyPatch, result: Any) -> None:
    def _urlopen(url: str, timeout: float) -> _Response:
        if isinstance(result, Exception):
            raise result
        return _Response(json.dumps(result).encode())

    monkeypatch.setattr(checker_module.urllib.request, "urlopen", _urlopen)


def test_returns_the_version_on_a_normal_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_urlopen(monkeypatch, {"info": {"version": "1.2.3"}})
    assert PypiVersionCheckerAdapter().latest_version("generic-ml-wrapper") == "1.2.3"


def test_network_failure_degrades_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_urlopen(monkeypatch, urllib.error.URLError("offline"))
    assert PypiVersionCheckerAdapter().latest_version("generic-ml-wrapper") is None


def test_http_error_degrades_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_urlopen(monkeypatch, urllib.error.HTTPError("u", 404, "not found", Message(), None))
    assert PypiVersionCheckerAdapter().latest_version("generic-ml-wrapper") is None


def test_malformed_json_degrades_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def _urlopen(url: str, timeout: float) -> _Response:
        return _Response(b"not json")

    monkeypatch.setattr(checker_module.urllib.request, "urlopen", _urlopen)
    assert PypiVersionCheckerAdapter().latest_version("generic-ml-wrapper") is None


def test_unexpected_shape_degrades_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_urlopen(monkeypatch, {"unexpected": "shape"})
    assert PypiVersionCheckerAdapter().latest_version("generic-ml-wrapper") is None


def test_empty_version_degrades_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_urlopen(monkeypatch, {"info": {"version": ""}})
    assert PypiVersionCheckerAdapter().latest_version("generic-ml-wrapper") is None
