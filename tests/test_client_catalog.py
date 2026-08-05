# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the client catalog: per-OS commands, version sources, prerequisites."""

from __future__ import annotations

import pytest

from generic_ml_wrapper.adapter.outbound.bootstrap.toml_client_catalog import (
    TomlClientCatalogAdapter,
)
from generic_ml_wrapper.application.domain.model.client_info import ClientInfo


def _client(name: str) -> ClientInfo:
    info = TomlClientCatalogAdapter().by_name(name)
    assert info is not None, f"{name} must be in the packaged catalogue"
    return info


def test_every_client_carries_the_setup_data() -> None:
    for info in TomlClientCatalogAdapter().supported():
        assert info.install_unix
        assert info.install_windows
        assert info.login
        assert info.binary
        assert info.display
        assert info.subscription
        assert info.version_probes  # at least one first-party source
        assert all(p.url for p in info.version_probes)
        assert all(p.kind in {"text", "json", "regex"} for p in info.version_probes)


def test_the_catalogue_lists_the_supported_clients_in_order() -> None:
    assert [info.name for info in TomlClientCatalogAdapter().supported()] == [
        "claude",
        "cursor",
        "codex",
        "vibe",
    ]


def test_an_unsupported_name_has_no_entry() -> None:
    assert TomlClientCatalogAdapter().by_name("nope") is None


@pytest.mark.parametrize(
    ("system", "expected"),
    [("Windows", "install_windows"), ("Darwin", "install_unix"), ("Linux", "install_unix")],
)
def test_install_for_selects_by_os(system: str, expected: str) -> None:
    claude = _client("claude")
    assert claude.install_for(system) == getattr(claude, expected)


def test_update_for_falls_back_to_the_installer_when_no_dedicated_updater() -> None:
    # Claude has a dedicated updater; Codex does not, so it re-runs its installer.
    assert _client("claude").update_for("Linux") == "claude update"
    codex = _client("codex")
    assert codex.update == ""
    assert codex.update_for("Linux") == codex.install_unix
    assert codex.update_for("Windows") == codex.install_windows


def test_only_vibe_needs_a_prerequisite_and_it_is_uv() -> None:
    uv = _client("vibe").prereq
    assert uv is not None
    assert uv.binary == "uv"
    assert uv.install_for("Windows") != uv.install_for("Linux")
    others = [info for info in TomlClientCatalogAdapter().supported() if info.name != "vibe"]
    assert all(info.prereq is None for info in others)


def test_resumable_flag_excludes_only_vibe() -> None:
    # What the clients listing tells the user, not how the launch works: claude/cursor are
    # told the id we named, codex learns the one it minted mid-run and binds it -- all three
    # resume. Only vibe keeps no durable session to reopen.
    assert _client("claude").resumable is True
    assert _client("cursor").resumable is True
    assert _client("codex").resumable is True
    assert _client("vibe").resumable is False
    resumable = {info.name for info in TomlClientCatalogAdapter().supported() if info.resumable}
    assert resumable == {"claude", "cursor", "codex"}


def test_only_codex_qualifies_its_resumable_yes() -> None:
    # Codex resumes a turn late (the id it minted has to be bound first), so its yes carries
    # a caveat -- a catalogue key, like login_hint, because the catalogue is data and data
    # does not know which language it will be read in.
    assert _client("codex").resume_hint == "client.resume_hint.codex"
    hinted = {info.name for info in TomlClientCatalogAdapter().supported() if info.resume_hint}
    assert hinted == {"codex"}  # everyone else's answer needs no footnote
