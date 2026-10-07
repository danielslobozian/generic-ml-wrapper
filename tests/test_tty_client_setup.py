# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the guided client setup: choose, update, install-and-verify, decline."""

from __future__ import annotations

import io

import pytest

from generic_ml_wrapper.adapter.outbound.bootstrap import tty_prompt
from generic_ml_wrapper.adapter.outbound.bootstrap.tty_client_setup import TtyClientSetup
from generic_ml_wrapper.application.domain.model.client_catalog import ClientInfo
from generic_ml_wrapper.application.port.outbound.client_version import ClientVersionPort
from generic_ml_wrapper.application.port.outbound.clipboard import ClipboardPort
from generic_ml_wrapper.application.port.outbound.command_runner import CommandRunnerPort
from generic_ml_wrapper.common.i18n import load_localizer

_I18N = load_localizer("en")

# What running a given install command makes appear on PATH (models the real effect).
_INSTALLS = {
    "astral.sh/uv": "uv",
    "mistral-vibe": "vibe",
    "claude.ai/install": "claude",
    "cursor.com/install": "cursor",
    "chatgpt.com/codex": "codex",
}


class _Tty(io.StringIO):
    """A StringIO that claims to be a terminal."""

    def isatty(self) -> bool:
        return True


class _Env:
    """Models PATH: binaries present now, or appearing after N presence checks."""

    def __init__(
        self, present: tuple[str, ...] = (), appear_after: dict[str, int] | None = None
    ) -> None:
        self._present = set(present)
        self._appear_after = dict(appear_after or {})
        self._checks: dict[str, int] = {}

    def present(self, binary: str) -> bool:
        self._checks[binary] = self._checks.get(binary, 0) + 1
        if binary in self._present:
            return True
        wanted = self._appear_after.get(binary)
        if wanted is not None and self._checks[binary] >= wanted:
            self._present.add(binary)
            return True
        return False

    def install(self, command: str) -> None:
        for needle, binary in _INSTALLS.items():
            if needle in command:
                self._present.add(binary)


class _FakeVersions(ClientVersionPort):
    def __init__(
        self, installed: dict[str, str] | None = None, latest: dict[str, str] | None = None
    ) -> None:
        self._installed = installed or {}
        self._latest = latest or {}

    def installed(self, info: ClientInfo) -> str | None:
        return self._installed.get(info.name)

    def latest(self, info: ClientInfo) -> str | None:
        return self._latest.get(info.name)


class _FakeRunner(CommandRunnerPort):
    def __init__(self, env: _Env) -> None:
        self._env = env
        self.commands: list[str] = []

    def run(self, command: str) -> int:
        self.commands.append(command)
        self._env.install(command)
        return 0


class _FakeClipboard(ClipboardPort):
    def __init__(self, *, ok: bool = True) -> None:
        self._ok = ok
        self.copied: list[str] = []

    def copy(self, text: str) -> bool:
        self.copied.append(text)
        return self._ok


def _wire(monkeypatch: pytest.MonkeyPatch, *, stdin: str, tty: bool = True) -> io.StringIO:
    stdin_stream: io.StringIO = _Tty(stdin) if tty else io.StringIO(stdin)
    err: io.StringIO = _Tty() if tty else io.StringIO()
    monkeypatch.setattr(tty_prompt.sys, "stdin", stdin_stream)
    monkeypatch.setattr(tty_prompt.sys, "stderr", err)
    return err


def _setup(
    env: _Env,
    *,
    versions: _FakeVersions | None = None,
    runner: _FakeRunner | None = None,
    clipboard: _FakeClipboard | None = None,
    sleeps: list[float] | None = None,
) -> TtyClientSetup:
    return TtyClientSetup(
        _I18N,
        version=versions or _FakeVersions(),
        runner=runner or _FakeRunner(env),
        clipboard=clipboard or _FakeClipboard(),
        present=env.present,
        sleep=(sleeps if sleeps is not None else []).append,
        system="Linux",
        poll_interval_s=0.0,
        poll_attempts=4,
    )


def test_non_tty_declines_to_the_lone_installed_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="1\n", tty=False)
    env = _Env(present=("claude",))
    assert _setup(env).choose(["claude"]) == "claude"
    assert _setup(_Env()).choose([]) is None


def test_picks_an_up_to_date_installed_client(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="1\n")  # pick the first menu entry (claude)
    env = _Env(present=("claude",))
    versions = _FakeVersions(installed={"claude": "2.1.215"}, latest={"claude": "2.1.215"})
    runner = _FakeRunner(env)
    assert _setup(env, versions=versions, runner=runner).choose(["claude"]) == "claude"
    assert runner.commands == []  # nothing to update


def test_a_client_ahead_of_the_channel_is_not_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    # Local build newer than the published channel (Claude stable lags npm) — no nag.
    err = _wire(monkeypatch, stdin="1\n")
    env = _Env(present=("claude",))
    versions = _FakeVersions(installed={"claude": "2.1.215"}, latest={"claude": "2.1.205"})
    runner = _FakeRunner(env)
    assert _setup(env, versions=versions, runner=runner).choose(["claude"]) == "claude"
    assert runner.commands == []
    assert "update available" not in err.getvalue()


def test_flags_a_stale_client_and_updates_it(monkeypatch: pytest.MonkeyPatch) -> None:
    err = _wire(monkeypatch, stdin="1\n1\n")  # pick claude, then "update now"
    env = _Env(present=("claude",))
    versions = _FakeVersions(installed={"claude": "2.1.200"}, latest={"claude": "2.1.215"})
    runner = _FakeRunner(env)
    assert _setup(env, versions=versions, runner=runner).choose(["claude"]) == "claude"
    assert "claude update" in runner.commands
    assert "update available" in err.getvalue()


def test_stale_client_can_be_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, stdin="1\n2\n")  # pick claude, then "keep"
    env = _Env(present=("claude",))
    versions = _FakeVersions(installed={"claude": "2.1.200"}, latest={"claude": "2.1.215"})
    runner = _FakeRunner(env)
    assert _setup(env, versions=versions, runner=runner).choose(["claude"]) == "claude"
    assert runner.commands == []


def test_installs_a_new_client_running_it_for_the_user(monkeypatch: pytest.MonkeyPatch) -> None:
    # No client installed: install another -> pick Vibe (#4) -> run uv, then run vibe.
    _wire(monkeypatch, stdin="1\n4\n1\n1\n")
    env = _Env()  # nothing present; the runner makes uv then vibe appear
    runner = _FakeRunner(env)
    clip = _FakeClipboard()
    assert _setup(env, runner=runner, clipboard=clip).choose([]) == "vibe"
    assert any("astral.sh/uv" in c for c in runner.commands)  # prerequisite first
    assert any("mistral-vibe" in c for c in runner.commands)
    assert clip.copied  # the command was offered on the clipboard


def test_self_install_polls_until_the_client_appears(monkeypatch: pytest.MonkeyPatch) -> None:
    # Install another -> Claude (#1) -> "I'll run it myself"; it appears on the 2nd poll.
    _wire(monkeypatch, stdin="1\n1\n2\n")
    env = _Env(appear_after={"claude": 2})
    runner = _FakeRunner(env)
    sleeps: list[float] = []
    assert _setup(env, runner=runner, sleeps=sleeps).choose([]) == "claude"
    assert runner.commands == []  # the user ran it, not gmlw
    assert len(sleeps) >= 1  # it waited at least one poll


def test_declining_the_install_target_keeps_the_existing_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Have claude, choose "install a different client" (#2), then skip the target menu.
    _wire(monkeypatch, stdin="2\n\n")
    env = _Env(present=("claude",))
    versions = _FakeVersions(installed={"claude": "2.1.215"})
    assert _setup(env, versions=versions).choose(["claude"]) == "claude"
