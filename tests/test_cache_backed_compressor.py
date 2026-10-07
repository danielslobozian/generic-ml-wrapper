# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the typed cache-backed context compressor (generic-ml-cache mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from generic_ml_cache_core.application.domain.model.execution.artifact import ArtifactType

from generic_ml_wrapper.adapter.outbound.compress import cache_backed_compressor
from generic_ml_wrapper.adapter.outbound.compress.cache_backed_compressor import (
    CacheBackedContextCompressor,
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


def _settings(prompts: dict[str, str]) -> config.CompressSettings:
    return config.CompressSettings(adapter="cursor", model="gpt-5.4", effort="low", prompts=prompts)


def test_stdout_returns_the_decoded_artifact() -> None:
    assert _stdout(_execution(stdout=b"hello")) == "hello"


def test_stdout_is_none_on_failure() -> None:
    assert _stdout(_execution(failure=object())) is None


def test_stdout_is_none_when_no_stdout_artifact() -> None:
    assert _stdout(_execution(stdout=None)) is None


def test_verbatim_when_no_prompt_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "compress", lambda: _settings({}))
    result = CacheBackedContextCompressor().compress("CTX", source_key="company", kind=None)
    assert result == "CTX"  # no key, no kind -> left verbatim


def test_compresses_using_the_kind_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    prompt_file = tmp_path / "human.md"
    prompt_file.write_text("compress, human", encoding="utf-8")
    monkeypatch.setattr(config, "compress", lambda: _settings({"human-touch": str(prompt_file)}))

    def _compress(*_a: object) -> MlExecution:
        return _execution(stdout=b"SMALL")

    monkeypatch.setattr(CacheBackedContextCompressor, "_compress", _compress)
    compressor = CacheBackedContextCompressor()
    assert compressor.compress("BIG", source_key="me.user", kind="human-touch") == "SMALL"


def test_unreadable_prompt_leaves_text_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "compress", lambda: _settings({"rules": "/no/such.md"}))
    result = CacheBackedContextCompressor().compress("CTX", source_key="rules", kind="rules")
    assert result == "CTX"


def test_compression_failure_leaves_text_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "r.md"
    prompt_file.write_text("compress", encoding="utf-8")
    monkeypatch.setattr(config, "compress", lambda: _settings({"rules": str(prompt_file)}))

    def _boom(*_args: object) -> object:
        raise RuntimeError("cache exploded")

    monkeypatch.setattr(CacheBackedContextCompressor, "_compress", _boom)
    result = CacheBackedContextCompressor().compress("CTX", source_key="rules", kind="rules")
    assert result == "CTX"


def test_module_exposes_the_compressor() -> None:
    assert issubclass(
        cache_backed_compressor.CacheBackedContextCompressor,
        cache_backed_compressor.ContextCompressorPort,
    )
