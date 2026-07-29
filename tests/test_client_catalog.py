# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the client catalog: per-OS commands, version sources, prerequisites."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model import client_catalog


def test_every_client_carries_the_setup_data() -> None:
    for info in client_catalog.SUPPORTED:
        assert info.install_unix
        assert info.install_windows
        assert info.login
        assert info.binary
        assert info.display
        assert info.subscription
        assert info.version_probes  # at least one first-party source
        assert all(p.url for p in info.version_probes)
        assert all(p.kind in {"text", "json", "regex"} for p in info.version_probes)


def test_install_for_selects_by_os() -> None:
    assert client_catalog.CLAUDE.install_for("Windows") == client_catalog.CLAUDE.install_windows
    assert client_catalog.CLAUDE.install_for("Darwin") == client_catalog.CLAUDE.install_unix
    assert client_catalog.CLAUDE.install_for("Linux") == client_catalog.CLAUDE.install_unix


def test_update_for_falls_back_to_the_installer_when_no_dedicated_updater() -> None:
    # Claude has a dedicated updater; Codex does not, so it re-runs its installer.
    assert client_catalog.CLAUDE.update_for("Linux") == "claude update"
    assert client_catalog.CODEX.update == ""
    assert client_catalog.CODEX.update_for("Linux") == client_catalog.CODEX.install_unix
    assert client_catalog.CODEX.update_for("Windows") == client_catalog.CODEX.install_windows


def test_only_vibe_needs_a_prerequisite_and_it_is_uv() -> None:
    assert client_catalog.VIBE.prereq is client_catalog.UV
    assert client_catalog.UV.binary == "uv"
    assert client_catalog.UV.install_for("Windows") != client_catalog.UV.install_for("Linux")
    assert all(
        info.prereq is None for info in client_catalog.SUPPORTED if info is not client_catalog.VIBE
    )


def test_resumable_flag_excludes_only_vibe() -> None:
    # What the clients listing tells the user, not how the launch works: claude/cursor are
    # told the id we named, codex learns the one it minted mid-run and binds it -- all three
    # resume. Only vibe keeps no durable session to reopen.
    assert client_catalog.CLAUDE.resumable is True
    assert client_catalog.CURSOR.resumable is True
    assert client_catalog.CODEX.resumable is True
    assert client_catalog.VIBE.resumable is False
    resumable = {info.name for info in client_catalog.SUPPORTED if info.resumable}
    assert resumable == {"claude", "cursor", "codex"}


def test_only_codex_qualifies_its_resumable_yes() -> None:
    # Codex resumes a turn late (the id it minted has to be bound first), so its yes carries
    # a caveat -- a catalogue key, like login_hint, because this data is built at import time.
    assert client_catalog.CODEX.resume_hint == "client.resume_hint.codex"
    hinted = {info.name for info in client_catalog.SUPPORTED if info.resume_hint}
    assert hinted == {"codex"}  # everyone else's answer needs no footnote
