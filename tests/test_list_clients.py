# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ListClients use case."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.domain.model.client_catalog import ClientInfo
from generic_ml_wrapper.application.usecase.list_clients import ListClientsUseCase


class _FakeDetector:
    def __init__(self, available: list[str]) -> None:
        self._available = available

    def available(self) -> list[str]:
        return self._available


class _FakeVersions:
    def __init__(self, versions: dict[str, str]) -> None:
        self._versions = versions
        self.probed: list[str] = []

    def installed(self, info: ClientInfo) -> str | None:
        self.probed.append(info.name)
        return self._versions.get(info.name)

    def latest(self, info: ClientInfo) -> str | None:  # unused by the use case
        raise AssertionError("latest must not be called")


def test_list_clients_composes_status_versions_and_default() -> None:
    detector = _FakeDetector(["claude", "cursor"])  # codex/vibe absent
    versions = _FakeVersions({"claude": "1.2.3"})  # cursor installed but version unreadable
    use_case = ListClientsUseCase(
        detector=detector,  # type: ignore[arg-type]
        version=versions,  # type: ignore[arg-type]
        default_client=lambda: "claude",
    )

    statuses = use_case.execute()

    by_name = {status.name: status for status in statuses}
    assert [status.name for status in statuses] == [info.name for info in client_catalog.SUPPORTED]
    assert by_name["claude"].installed is True
    assert by_name["claude"].version == "1.2.3"
    assert by_name["claude"].is_default is True
    assert by_name["cursor"].installed is True
    assert by_name["cursor"].version is None  # installed, but --version unreadable
    assert by_name["codex"].installed is False
    assert by_name["codex"].resumable is False  # from the catalog
    assert by_name["claude"].resumable is True


def test_list_clients_skips_version_probe_for_absent_clients() -> None:
    versions = _FakeVersions({})
    use_case = ListClientsUseCase(
        detector=_FakeDetector(["claude"]),  # type: ignore[arg-type]
        version=versions,  # type: ignore[arg-type]
        default_client=lambda: "claude",
    )

    use_case.execute()

    assert versions.probed == ["claude"]  # the subprocess is not run for uninstalled clients
