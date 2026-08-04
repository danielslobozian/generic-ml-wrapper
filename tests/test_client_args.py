# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for splitting a passthrough argument string into launch tokens."""

from __future__ import annotations

import os

from generic_ml_wrapper.application.domain.model.client_arguments import ClientArguments


def test_a_plain_flag_becomes_one_token() -> None:
    assert ClientArguments.parse("--dangerously-skip-permissions").tokens == (
        "--dangerously-skip-permissions",
    )


def test_several_flags_become_several_tokens() -> None:
    assert ClientArguments.parse("--yolo --verbose").tokens == ("--yolo", "--verbose")


# What a quoted value looks like once split, per platform. Windows splits in non-posix
# mode on purpose (there a backslash is a path separator, not an escape), which leaves the
# quotes inside the token -- subprocess re-quotes it correctly on that side. The claim the
# tests make is the same either way: it is *one* token.
QUOTED_PATH = "/two words" if os.name != "nt" else '"/two words"'


def test_a_quoted_value_stays_one_token() -> None:
    # The whole point of shell-splitting rather than str.split: a path with a space must
    # arrive as a single argument, not two.
    assert ClientArguments.parse('--add-dir "/two words"').tokens == ("--add-dir", QUOTED_PATH)


def test_blank_and_whitespace_yield_no_tokens() -> None:
    assert ClientArguments.parse("").tokens == ()
    assert ClientArguments.parse("   ").tokens == ()


def test_blank_input_is_not_a_parse_failure() -> None:
    assert ClientArguments.parse("").unparseable == ""


def test_an_unbalanced_quote_yields_no_tokens_and_carries_the_reason() -> None:
    # A typo must not take down the launch -- but it must not pass unmentioned either:
    # silently dropping the flags starts the client without them and looks like success.
    # The domain records *that* it failed; reporting it is the caller's job.
    arguments = ClientArguments.parse('--foo "unclosed')
    assert arguments.tokens == ()
    assert arguments.unparseable != ""
