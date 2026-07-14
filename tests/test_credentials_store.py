# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the filesystem credentials store and the SetCredential use case."""

import sys
import tomllib
from pathlib import Path

import pytest

from generic_ml_wrapper.adapter.outbound.credentials.filesystem_credentials_store import (
    CredentialsUnreadableError,
    FilesystemCredentialsStore,
)
from generic_ml_wrapper.application.port.inbound.set_credential import SetCredentialCommand
from generic_ml_wrapper.application.usecase.set_credential import SetCredentialUseCase


def test_set_then_resolve_roundtrips(tmp_path: Path) -> None:
    store = FilesystemCredentialsStore(tmp_path / "credentials.toml")
    store.set("doc-review", "GITHUB_TOKEN", "ghp_secret")
    assert store.resolve("doc-review") == {"GITHUB_TOKEN": "ghp_secret"}


def test_resolve_unknown_workflow_is_empty(tmp_path: Path) -> None:
    assert FilesystemCredentialsStore(tmp_path / "none.toml").resolve("doc-review") == {}


def test_set_groups_by_workflow_and_replaces(tmp_path: Path) -> None:
    store = FilesystemCredentialsStore(tmp_path / "credentials.toml")
    store.set("deploy", "AWS_ACCESS_KEY_ID", "AKIA1")
    store.set("deploy", "AWS_SECRET_ACCESS_KEY", "s3cr3t")
    store.set("doc-review", "GITHUB_TOKEN", "ghp_1")
    store.set("doc-review", "GITHUB_TOKEN", "ghp_2")  # replaces

    assert store.resolve("deploy") == {
        "AWS_ACCESS_KEY_ID": "AKIA1",
        "AWS_SECRET_ACCESS_KEY": "s3cr3t",
    }
    assert store.resolve("doc-review") == {"GITHUB_TOKEN": "ghp_2"}
    # The written file is valid TOML with a table per workflow.
    parsed = tomllib.loads((tmp_path / "credentials.toml").read_text(encoding="utf-8"))
    assert set(parsed) == {"deploy", "doc-review"}


def test_set_escapes_special_characters(tmp_path: Path) -> None:
    store = FilesystemCredentialsStore(tmp_path / "credentials.toml")
    tricky = 'a"b\\c\ttab'
    store.set("wf", "TOKEN", tricky)
    assert store.resolve("wf") == {"TOKEN": tricky}  # survives a write/read round-trip


def test_file_is_owner_only_on_posix(tmp_path: Path) -> None:
    if sys.platform.startswith("win"):
        return  # Windows does not honor POSIX mode bits
    path = tmp_path / "credentials.toml"
    FilesystemCredentialsStore(path).set("wf", "TOKEN", "x")
    assert (path.stat().st_mode & 0o777) == 0o600


def test_use_case_delegates_to_the_store(tmp_path: Path) -> None:
    store = FilesystemCredentialsStore(tmp_path / "credentials.toml")
    SetCredentialUseCase(store).execute(SetCredentialCommand("wf", "TOKEN", "v"))
    assert store.resolve("wf") == {"TOKEN": "v"}


def test_corrupt_file_aborts_set_and_leaves_secrets_intact(tmp_path: Path) -> None:
    path = tmp_path / "credentials.toml"
    path.write_text('[deploy]\nTOKEN = "no close', encoding="utf-8")  # unterminated: invalid TOML
    before = path.read_bytes()
    with pytest.raises(CredentialsUnreadableError):
        FilesystemCredentialsStore(path).set("deploy", "OTHER", "new")
    assert path.read_bytes() == before  # never overwritten


def test_corrupt_file_makes_resolve_raise(tmp_path: Path) -> None:
    path = tmp_path / "credentials.toml"
    path.write_text('x = "no close', encoding="utf-8")
    with pytest.raises(CredentialsUnreadableError):
        FilesystemCredentialsStore(path).resolve("deploy")
