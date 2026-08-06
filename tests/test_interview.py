# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the setup interview — the terminal's side of ``gmlw init``.

Driven through a stubbed stdin rather than by patching the choosers, so what is
exercised is the sequence the interview actually runs: which questions are asked, in
what order, and the two ways it can end without an answer.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from generic_ml_wrapper.adapter.inbound.cli.setup import interview as interview_module
from generic_ml_wrapper.adapter.inbound.cli.setup.interview import run_interview
from generic_ml_wrapper.application.domain.model.client_info import ClientInfo
from generic_ml_wrapper.application.domain.model.init_answers import InitAnswers
from generic_ml_wrapper.application.port.inbound.listed_client import ListedClient
from generic_ml_wrapper.application.wiring.localization import load_localizer

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.inbound.cli.setup.message_source import MessageSource

_EN = load_localizer("en")


def _localizer_for(_code: str) -> MessageSource:
    return _EN


def _client(name: str, *, installed: bool) -> ListedClient:
    return ListedClient(
        name=name,
        display=name.title(),
        installed=installed,
        version="1.0.0" if installed else None,
        resumable=True,
        is_default=False,
    )


def _supported() -> tuple[ClientInfo, ...]:
    return (
        ClientInfo(
            name="claude",
            binary="claude",
            display="Claude Code",
            subscription="",
            install_unix="npm i -g claude",
            install_windows="npm i -g claude",
            login="claude",
        ),
    )


def _run(clients: list[ListedClient]) -> InitAnswers | None:
    return run_interview(
        languages=["en", "fr"],
        default_language="en",
        default_name="Dan",
        personas=[],
        clients=clients,
        supported=_supported(),
        system="Linux",
        localizer_for=_localizer_for,
        seed=_EN,
    )


def test_no_client_installed_stops_and_shows_the_install_commands(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A client is a prerequisite, not an answer: the interview ends before asking anything
    # else, so nothing can be persisted from a half-finished setup.
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert _run([_client("claude", installed=False)]) is None
    printed = capsys.readouterr().err
    assert "npm i -g claude" in printed  # the reason the run stopped, even off a terminal


def test_a_full_run_comes_back_as_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Every prompt declines to its default off a terminal, which is what makes a
    # non-interactive run complete rather than block.
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    answers = _run([_client("claude", installed=True)])

    assert answers is not None
    assert answers.language == "en"
    assert answers.client == "claude"
    assert answers.role.slug == interview_module.DEFAULT_ROLE
    assert answers.environment.slug == interview_module.DEFAULT_ENVIRONMENT


def test_a_lone_installed_client_is_taken_without_asking(monkeypatch: pytest.MonkeyPatch) -> None:
    # One option is not a choice. Off a terminal the announcement is silent, but the
    # selection still happens -- which is what makes a scripted setup complete.
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    answers = _run([_client("claude", installed=True), _client("codex", installed=False)])

    assert answers is not None
    assert answers.client == "claude"


def test_the_language_question_is_asked_before_anything_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # It sets the voice the rest is asked in, so it cannot come second.
    asked: list[str] = []
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    def _record(code: str) -> MessageSource:
        asked.append(code)
        return _EN

    run_interview(
        languages=["en", "fr"],
        default_language="en",
        default_name="Dan",
        personas=[],
        clients=[_client("claude", installed=True)],
        supported=_supported(),
        system="Linux",
        localizer_for=_record,
        seed=_EN,
    )
    assert asked == ["en"]  # the catalogue is built once, from the answer to question one
