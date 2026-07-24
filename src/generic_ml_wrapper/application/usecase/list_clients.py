# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListClients use case: the supported clients with their install status and version."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.domain.model import client_catalog
from generic_ml_wrapper.application.port.inbound.list_clients import ClientStatus, ListClients

if TYPE_CHECKING:
    from collections.abc import Callable

    from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
    from generic_ml_wrapper.application.port.outbound.client_version import ClientVersionPort


class ListClientsUseCase(ListClients):
    """Compose the client catalog with PATH detection, versions, and the default setting."""

    def __init__(
        self,
        detector: ClientDetectorPort,
        version: ClientVersionPort,
        default_client: Callable[[], str],
    ) -> None:
        """Wire the use case to its data sources.

        Args:
            detector: Lists the client names currently on ``PATH``.
            version: Reads a client's installed on-disk version (best-effort).
            default_client: Returns the configured default client id.
        """
        self._detector = detector
        self._version = version
        self._default_client = default_client

    def execute(self) -> list[ClientStatus]:
        """Build one status per supported client (versions read only for installed ones)."""
        available = set(self._detector.available())
        default = self._default_client()
        statuses: list[ClientStatus] = []
        for info in client_catalog.SUPPORTED:
            installed = info.name in available
            statuses.append(
                ClientStatus(
                    name=info.name,
                    display=info.display,
                    installed=installed,
                    version=self._version.installed(info) if installed else None,
                    resumable=info.resumable,
                    is_default=info.name == default,
                )
            )
        return statuses
