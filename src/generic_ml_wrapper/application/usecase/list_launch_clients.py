# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListLaunchClientsUseCase use case: the catalog, PATH detection, and the default."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.launch_client import LaunchClient
from generic_ml_wrapper.application.port.inbound.list_launch_clients import ListLaunchClientsUseCase

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.application.port.outbound.client_catalog import ClientCatalogPort
    from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort


class ListLaunchClientsService(ListLaunchClientsUseCase):
    """Compose PATH detection, the ``[callers]`` overrides, and the configured default.

    The version-reading sibling of this is
    :class:`~generic_ml_wrapper.application.usecase.list_clients.ListClientsService`, which
    answers "what do I have installed, and is it current" for the Clients view. This one
    answers "what can I launch on", which is a cheaper question and a different one.

    ``[callers]`` is not a decoration on the catalog -- it is a source of clients in its own
    right. ``DefaultCliCallerProviderAdapter`` looks an override up **by name before** it considers
    any built-in, so an entry like ``cursor-mitm = "…:CursorMitmCaller"`` makes
    ``cursor-mitm`` as real a client as ``claude``, with no catalog entry and no binary gmlw
    knows about. A chooser built from the catalog alone would be the one place in gmlw where
    those clients did not exist.
    """

    def __init__(
        self,
        detector: ClientDetectorPort,
        default_client: Callable[[], str],
        caller_overrides: Callable[[], dict[str, str]],
        catalog: ClientCatalogPort,
    ) -> None:
        """Wire the use case to PATH detection, the default, and the configured callers.

        Args:
            detector: Lists the built-in client names currently on ``PATH``.
            default_client: Returns the configured default client id.
            caller_overrides: Returns the ``[callers]`` mapping of client name to spec.
            catalog: The supported built-in clients.
        """
        self._detector = detector
        self._default_client = default_client
        self._caller_overrides = caller_overrides
        self._catalog = catalog

    def execute(self) -> list[LaunchClient]:
        """List what can be launched on: installed built-ins, then configured callers."""
        available = set(self._detector.available())
        configured = self._caller_overrides()
        default = self._default_client()
        clients = [
            LaunchClient(
                name=info.name,
                display=info.display,
                is_default=info.name == default,
                custom=info.name in configured,
            )
            # A configured caller for a built-in name is offered whatever PATH says: the
            # override decides what actually runs, and it may not be that binary at all.
            for info in self._catalog.supported()
            if info.name in available or info.name in configured
        ]
        known = {info.name for info in self._catalog.supported()}
        clients += [
            LaunchClient(name=name, display=name, is_default=name == default, custom=True)
            for name in sorted(configured)
            if name not in known
        ]
        return clients
