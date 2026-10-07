# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the InterceptorChain and its config-driven construction."""

from pathlib import Path

import pytest

from generic_ml_wrapper.application.domain.service.interceptor_chain import InterceptorChain
from generic_ml_wrapper.application.port.outbound.interceptor import InterceptorPort
from generic_ml_wrapper.application.wiring import composition
from generic_ml_wrapper.common.spec_loader import SpecLoadError


class _Wrap(InterceptorPort):
    def __init__(self, tag: str) -> None:
        self._tag = tag

    def intercept(self, text: str, target: str) -> str:
        return f"{text}[{self._tag}:{target}]"


def test_empty_chain_is_the_identity() -> None:
    assert InterceptorChain(()).apply("rules", "x") == "x"


def test_has_reports_configured_targets() -> None:
    chain = InterceptorChain([("request", _Wrap("a"))])
    assert chain.has("request") is True
    assert chain.has("response") is False


def test_only_matching_targets_run_in_order() -> None:
    chain = InterceptorChain(
        [("rules", _Wrap("a")), ("profile", _Wrap("b")), ("rules", _Wrap("c"))]
    )
    assert chain.apply("rules", "x") == "x[a:rules][c:rules]"  # both rules, in order, target passed
    assert chain.apply("profile", "y") == "y[b:profile]"
    assert chain.apply("context", "z") == "z"  # no interceptor for this target


def _write_interceptor(tmp_path: Path) -> str:
    module = tmp_path / "shout.py"
    module.write_text(
        "from generic_ml_wrapper.application.port.outbound.interceptor import InterceptorPort\n"
        "class Shout(InterceptorPort):\n"
        "    def intercept(self, text: str, target: str) -> str:\n"
        "        return text.upper()\n",
        encoding="utf-8",
    )
    return f"{module}:Shout"


def test_chain_is_built_from_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec = _write_interceptor(tmp_path)
    monkeypatch.setattr(composition.config, "interceptors", lambda: [("rules", spec)])
    chain = composition._interceptor_chain()
    assert chain.apply("rules", "quiet") == "QUIET"


def test_unloadable_interceptor_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # A configured-but-unloadable interceptor is a config error, surfaced -- not skipped.
    monkeypatch.setattr(composition.config, "interceptors", lambda: [("rules", "no.such:Thing")])
    with pytest.raises(SpecLoadError):
        composition._interceptor_chain()
