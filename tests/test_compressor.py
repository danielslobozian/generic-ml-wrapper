# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the context compressor interceptor (generic-ml-cache API mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from generic_ml_cache_core.application.domain.model.execution.artifact import ArtifactType

from generic_ml_wrapper.adapter.outbound.interceptor import compressor
from generic_ml_wrapper.adapter.outbound.interceptor.compressor import (
    CompressorInterceptor,
    _stdout,
)
from generic_ml_wrapper.common import config

if TYPE_CHECKING:
    from pathlib import Path

    from generic_ml_cache_core.application.domain.model.execution.ml_execution import MlExecution


def _execution(*, failure: object = None, stdout: bytes | None = b"COMPRESSED") -> MlExecution:
    artifacts: list[object] = []
    if stdout is not None:
        artifacts.append(
            SimpleNamespace(artifact_type=ArtifactType.STDOUT, content=stdout, encoding="utf-8")
        )
    return cast("MlExecution", SimpleNamespace(failure=failure, artifacts=artifacts))


def _settings(prompt: str | None) -> config.CompressSettings:
    return config.CompressSettings(prompt=prompt, adapter="cursor", model="gpt-5.4", effort="low")


def test_stdout_returns_the_decoded_artifact() -> None:
    assert _stdout(_execution(stdout=b"hello")) == "hello"


def test_stdout_is_none_on_failure() -> None:
    assert _stdout(_execution(failure=object())) is None


def test_stdout_is_none_when_no_stdout_artifact() -> None:
    assert _stdout(_execution(stdout=None)) is None


def test_compression_is_off_without_a_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "compress", lambda: _settings(None))
    assert CompressorInterceptor().intercept("CONTEXT", "context") == "CONTEXT"


def test_compresses_when_configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    prompt_file = tmp_path / "compress.md"
    prompt_file.write_text("compress this", encoding="utf-8")
    monkeypatch.setattr(config, "compress", lambda: _settings(str(prompt_file)))

    def _compress(*_a: object) -> MlExecution:
        return _execution(stdout=b"SMALL")

    monkeypatch.setattr(CompressorInterceptor, "_compress", _compress)
    assert CompressorInterceptor().intercept("BIG CONTEXT", "context") == "SMALL"


def test_unreadable_prompt_leaves_text_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "compress", lambda: _settings("/no/such/prompt.md"))
    assert CompressorInterceptor().intercept("CONTEXT", "context") == "CONTEXT"


def test_compression_failure_leaves_text_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "compress.md"
    prompt_file.write_text("compress this", encoding="utf-8")
    monkeypatch.setattr(config, "compress", lambda: _settings(str(prompt_file)))

    def _boom(*_args: object) -> object:
        raise RuntimeError("cache exploded")

    monkeypatch.setattr(CompressorInterceptor, "_compress", _boom)
    assert CompressorInterceptor().intercept("CONTEXT", "context") == "CONTEXT"


def test_module_exposes_the_interceptor() -> None:
    assert issubclass(compressor.CompressorInterceptor, compressor.InterceptorPort)
