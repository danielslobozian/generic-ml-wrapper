# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the CheckClientReady use case and the client catalog."""

from generic_ml_wrapper.adapter.outbound.bootstrap.toml_client_catalog import TomlClientCatalog
from generic_ml_wrapper.application.port.inbound.check_client_ready import ClientReadiness
from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
from generic_ml_wrapper.application.usecase.check_client_ready import CheckClientReadyUseCase


class _FakeDetector(ClientDetectorPort):
    def __init__(self, installed: list[str]) -> None:
        self._installed = installed

    def available(self) -> list[str]:
        return self._installed


def _check(
    client: str, *, installed: list[str], overrides: dict[str, str] | None = None
) -> ClientReadiness:
    return CheckClientReadyUseCase(
        overrides=overrides or {},
        detector=_FakeDetector(installed),
        catalog=TomlClientCatalog(),
    ).execute(client)


def test_installed_built_in_is_ready() -> None:
    readiness = _check("claude", installed=["claude", "codex"])
    assert readiness.ready is True
    assert readiness.missing is None


def test_missing_built_in_is_not_ready_with_its_catalog_entry() -> None:
    readiness = _check("cursor", installed=["claude"])
    assert readiness.ready is False
    assert readiness.missing is TomlClientCatalog().by_name("cursor")
    assert readiness.installed == ("claude",)  # so the CLI can suggest an alternative


def test_override_is_trusted_without_a_path_check() -> None:
    # a private caller (e.g. cursor-mitm) resolves to code, not a PATH binary
    readiness = _check("cursor-mitm", installed=[], overrides={"cursor-mitm": "x.py:C"})
    assert readiness.ready is True
    assert readiness.missing is None


def test_unknown_client_is_not_ready_and_has_no_catalog_entry() -> None:
    readiness = _check("weaver", installed=["claude"])
    assert readiness.ready is False
    assert readiness.missing is None  # not a supported built-in -> nothing to install


def test_catalog_covers_every_built_in_client() -> None:
    assert {info.name for info in TomlClientCatalog().supported()} == {
        "claude",
        "cursor",
        "codex",
        "vibe",
    }
    assert TomlClientCatalog().by_name("cursor") is TomlClientCatalog().by_name("cursor")
    assert TomlClientCatalog().by_name("nope") is None
    assert all(
        info.install_unix and info.install_windows and info.login and info.binary
        for info in TomlClientCatalog().supported()
    )
