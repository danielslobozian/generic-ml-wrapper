# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the terminal language chooser."""

import io

import pytest

from generic_ml_wrapper.adapter.inbound.cli.setup import tty_prompt
from generic_ml_wrapper.adapter.inbound.cli.setup.tty_language_chooser import (
    TtyLanguageChooser,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.json_catalog_message_source import (
    JsonCatalogMessageSource,
)
from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
    MessageSourceAccessor,
)


def _accessor(language: str) -> MessageSourceAccessor:
    return MessageSourceAccessor(JsonCatalogMessageSource(), language)


_I18N = _accessor("en")
_LANGS = ["en", "fr"]


class _Tty(io.StringIO):
    """A StringIO that claims to be a terminal."""

    def isatty(self) -> bool:
        return True


def _wire(monkeypatch: pytest.MonkeyPatch, *, stdin: str, tty: bool = True) -> io.StringIO:
    stdin_stream: io.StringIO = _Tty(stdin) if tty else io.StringIO(stdin)
    err: io.StringIO = _Tty() if tty else io.StringIO()
    monkeypatch.setattr(tty_prompt.sys, "stdin", stdin_stream)
    monkeypatch.setattr(tty_prompt.sys, "stderr", err)
    return err


def test_resolves_to_default_when_not_a_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="2\n", tty=False)
    # Never blocks, never returns None: a language must resolve for the rest of init.
    assert TtyLanguageChooser(_I18N).choose(_LANGS, "fr") == "fr"


def test_a_number_selects_that_language(monkeypatch: pytest.MonkeyPatch) -> None:
    err = _wire(monkeypatch, stdin="2\n")
    assert TtyLanguageChooser(_I18N).choose(_LANGS, "en") == "fr"
    prompt = err.getvalue()
    assert "1) English" in prompt  # endonyms, not raw codes
    assert "2) Français" in prompt


def test_empty_line_takes_the_default_language(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="\n")
    assert TtyLanguageChooser(_I18N).choose(_LANGS, "fr") == "fr"


def test_default_absent_from_the_list_falls_back_to_the_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire(monkeypatch, stdin="\n")
    assert TtyLanguageChooser(_I18N).choose(_LANGS, "de") == "en"  # unknown default -> index 0


def test_end_of_input_resolves_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="")  # EOF
    assert TtyLanguageChooser(_I18N).choose(_LANGS, "en") == "en"
