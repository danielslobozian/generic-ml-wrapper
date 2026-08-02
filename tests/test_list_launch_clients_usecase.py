# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ListLaunchClients use case: the catalog, PATH, and the default."""

from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
from generic_ml_wrapper.application.usecase.list_launch_clients import ListLaunchClientsUseCase


class FakeDetector(ClientDetectorPort):
    def __init__(self, available: list[str]) -> None:
        self._available = available

    def available(self) -> list[str]:
        return list(self._available)


def _use_case(available: list[str], default: str = "claude") -> ListLaunchClientsUseCase:
    return ListLaunchClientsUseCase(FakeDetector(available), lambda: default)


def test_every_supported_client_is_offered() -> None:
    """Absent clients are listed too — an absence you can see beats one you cannot."""
    clients = _use_case([]).execute()

    assert [c.name for c in clients] == [info.name for info in client_catalog.SUPPORTED]


def test_installed_reflects_what_is_on_path() -> None:
    clients = {c.name: c for c in _use_case(["claude", "codex"]).execute()}

    assert clients["claude"].installed is True
    assert clients["codex"].installed is True
    assert clients["vibe"].installed is False


def test_exactly_the_configured_client_is_flagged_default() -> None:
    clients = _use_case(["claude", "codex"], default="codex").execute()

    assert [c.name for c in clients if c.is_default] == ["codex"]


def test_a_default_that_is_not_installed_is_still_the_default() -> None:
    """The picker has to be able to say "your default is missing" rather than hide it."""
    clients = {c.name: c for c in _use_case([], default="claude").execute()}

    assert clients["claude"].is_default is True
    assert clients["claude"].installed is False


def test_the_display_name_comes_from_the_catalog() -> None:
    clients = {c.name: c for c in _use_case(["claude"]).execute()}
    expected = next(i.display for i in client_catalog.SUPPORTED if i.name == "claude")

    assert clients["claude"].display == expected
