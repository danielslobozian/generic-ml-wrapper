# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the help banner."""

import io

import pytest

from generic_ml_wrapper.adapter.inbound.cli import banner as banner_module
from generic_ml_wrapper.adapter.inbound.cli.banner import banner


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_banner_is_plain_when_not_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(banner_module.sys, "stdout", io.StringIO())  # isatty() is False
    text = banner()
    assert "gmlw" in text
    assert "a wrapper around an ML coding CLI" in text
    assert "\033" not in text  # no ANSI when piped


def test_banner_is_colored_at_a_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(banner_module.sys, "stdout", _Tty())
    assert "\033[" in banner()
