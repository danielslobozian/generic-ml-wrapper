# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Tests for ListLaunchClients: what a launch can actually be pointed at.

Two sources, two different rules. A built-in counts only when its binary is on ``PATH``.
A ``[callers]`` entry counts unconditionally — gmlw has no idea what that caller needs,
and configuring one is already the statement that it works.
"""

from generic_ml_wrapper.adapter.outbound.bootstrap.toml_client_catalog import TomlClientCatalog
from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
from generic_ml_wrapper.application.usecase.list_launch_clients import ListLaunchClientsUseCase


class FakeDetector(ClientDetectorPort):
    def __init__(self, available: list[str]) -> None:
        self._available = available

    def available(self) -> list[str]:
        return list(self._available)


def _use_case(
    available: list[str],
    default: str = "claude",
    callers: dict[str, str] | None = None,
) -> ListLaunchClientsUseCase:
    return ListLaunchClientsUseCase(
        FakeDetector(available),
        lambda: default,
        lambda: dict(callers or {}),
        TomlClientCatalog(),
    )


def test_only_installed_built_ins_are_offered() -> None:
    """Offering a client that is not installed is offering a launch that cannot happen."""
    clients = _use_case(["claude", "codex"]).execute()

    assert [c.name for c in clients] == ["claude", "codex"]


def test_nothing_installed_and_nothing_configured_offers_nothing() -> None:
    assert _use_case([]).execute() == []


def test_installed_built_ins_keep_catalog_order() -> None:
    order = [info.name for info in TomlClientCatalog().supported()]
    clients = _use_case(order[::-1]).execute()

    assert [c.name for c in clients] == order


def test_a_configured_caller_gmlw_does_not_ship_is_offered() -> None:
    """`[callers] cursor-mitm = "…:CursorMitmCaller"` makes cursor-mitm a real client."""
    clients = _use_case(["claude"], callers={"cursor-mitm": "/plugins/cursor_mitm.py:C"}).execute()

    assert [c.name for c in clients] == ["claude", "cursor-mitm"]
    custom = clients[1]
    assert custom.custom is True
    assert custom.display == "cursor-mitm"  # no catalog entry to take a nicer name from


def test_a_configured_caller_is_offered_even_when_its_binary_is_absent() -> None:
    """gmlw cannot PATH-check a caller it did not write — the config is the statement."""
    clients = _use_case([], callers={"cursor-mitm": "/plugins/cursor_mitm.py:C"}).execute()

    assert [c.name for c in clients] == ["cursor-mitm"]


def test_overriding_a_built_in_offers_it_whatever_path_says() -> None:
    """The override decides what runs; it may not be that binary at all."""
    clients = {
        c.name: c for c in _use_case([], callers={"cursor": "/plugins/cursor_mitm.py:C"}).execute()
    }

    assert "cursor" in clients
    assert clients["cursor"].custom is True
    assert clients["cursor"].display != "cursor"  # keeps the catalog's human name


def test_an_overridden_built_in_is_not_listed_twice() -> None:
    clients = _use_case(["cursor"], callers={"cursor": "/plugins/cursor_mitm.py:C"}).execute()

    assert [c.name for c in clients] == ["cursor"]


def test_an_installed_built_in_without_an_override_is_not_custom() -> None:
    (only,) = _use_case(["claude"]).execute()

    assert only.custom is False


def test_exactly_the_configured_client_is_flagged_default() -> None:
    clients = _use_case(["claude", "codex"], default="codex").execute()

    assert [c.name for c in clients if c.is_default] == ["codex"]


def test_a_custom_client_can_be_the_default() -> None:
    clients = _use_case(
        ["claude"], default="cursor-mitm", callers={"cursor-mitm": "/p.py:C"}
    ).execute()

    assert [c.name for c in clients if c.is_default] == ["cursor-mitm"]


def test_a_default_that_is_not_available_simply_has_no_row() -> None:
    """Nothing to mark, and nothing to launch on — the picker starts at the top instead."""
    clients = _use_case(["codex"], default="claude").execute()

    assert [c.name for c in clients] == ["codex"]
    assert not [c for c in clients if c.is_default]


def test_custom_names_are_sorted_so_the_list_is_stable() -> None:
    callers = {"zeta": "/z.py:C", "alpha": "/a.py:C"}
    clients = _use_case([], callers=callers).execute()

    assert [c.name for c in clients] == ["alpha", "zeta"]


def test_the_display_name_comes_from_the_catalog() -> None:
    (only,) = _use_case(["claude"]).execute()
    expected = next(i.display for i in TomlClientCatalog().supported() if i.name == "claude")

    assert only.display == expected
