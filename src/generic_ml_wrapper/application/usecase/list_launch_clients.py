# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListLaunchClients use case: the catalog, PATH detection, and the default."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.port.inbound.list_launch_clients import (
    LaunchClient,
    ListLaunchClients,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort


class ListLaunchClientsUseCase(ListLaunchClients):
    """Compose the client catalog with PATH detection and the configured default.

    The version-reading sibling of this is
    :class:`~generic_ml_wrapper.application.usecase.list_clients.ListClientsUseCase`, which
    answers "what do I have installed, and is it current" for the Clients view. This one
    answers "what can I launch on", which is a cheaper question and a different one.
    """

    def __init__(self, detector: ClientDetectorPort, default_client: Callable[[], str]) -> None:
        """Wire the use case to PATH detection and the default-client setting.

        Args:
            detector: Lists the client names currently on ``PATH``.
            default_client: Returns the configured default client id.
        """
        self._detector = detector
        self._default_client = default_client

    def execute(self) -> list[LaunchClient]:
        """List the supported clients, flagging what is installed and which is default."""
        available = set(self._detector.available())
        default = self._default_client()
        return [
            LaunchClient(
                name=info.name,
                display=info.display,
                installed=info.name in available,
                is_default=info.name == default,
            )
            for info in client_catalog.SUPPORTED
        ]
