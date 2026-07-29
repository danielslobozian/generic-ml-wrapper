# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for splitting a passthrough argument string into launch tokens."""

from __future__ import annotations

import os

import pytest

from generic_ml_wrapper.application.domain.service.diagnostics import Diagnostics
from generic_ml_wrapper.common import client_args
from generic_ml_wrapper.common.log import set_active


class _Recording(Diagnostics):
    """A sink that keeps what it was handed, so a test can assert the drop was reported."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, object]]] = []

    def debug(self, message: str, **context: object) -> None:
        self.records.append(("debug", context))

    def info(self, message: str, **context: object) -> None:
        self.records.append(("info", context))

    def warning(self, message: str, **context: object) -> None:
        self.records.append(("warning", context))

    def error(self, message: str, exc: BaseException | None = None, **context: object) -> None:
        self.records.append(("error", context))

    def keys(self, level: str) -> list[object]:
        """The catalogue keys logged at *level* — asserted on rather than rendered text."""
        return [context.get("key") for name, context in self.records if name == level]


def test_a_plain_flag_becomes_one_token() -> None:
    assert client_args.split("--dangerously-skip-permissions") == (
        "--dangerously-skip-permissions",
    )


def test_several_flags_become_several_tokens() -> None:
    assert client_args.split("--yolo --verbose") == ("--yolo", "--verbose")


# What a quoted value looks like once split, per platform. Windows splits in non-posix
# mode on purpose (there a backslash is a path separator, not an escape), which leaves the
# quotes inside the token -- subprocess re-quotes it correctly on that side. The claim the
# tests make is the same either way: it is *one* token.
QUOTED_PATH = "/two words" if os.name != "nt" else '"/two words"'


def test_a_quoted_value_stays_one_token() -> None:
    # The whole point of shell-splitting rather than str.split: a path with a space must
    # arrive as a single argument, not two.
    assert client_args.split('--add-dir "/two words"') == ("--add-dir", QUOTED_PATH)


def test_blank_and_whitespace_yield_no_tokens() -> None:
    assert client_args.split("") == ()
    assert client_args.split("   ") == ()


def test_an_unbalanced_quote_yields_no_tokens_but_says_so(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A typo must not take down the launch -- but it must not pass unmentioned either:
    # silently dropping the flags starts the client without them and looks like success.
    sink = _Recording()
    previous = set_active(sink)
    try:
        assert client_args.split('--foo "unclosed') == ()
    finally:
        set_active(previous)
    assert "log.client_args_unparseable" in sink.keys("warning"), (
        "the dropped arguments must be reported"
    )
    assert capsys.readouterr().err == "", "and not by dumping a traceback on the client's screen"
