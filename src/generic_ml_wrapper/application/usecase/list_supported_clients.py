# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListSupportedClientsUseCase use case: the catalogue, without saying where it comes from."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_supported_clients import (
    ListSupportedClientsUseCase,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_info import ClientInfo
    from generic_ml_wrapper.application.port.outbound.client_catalog import ClientCatalogPort


class ListSupportedClientsService(ListSupportedClientsUseCase):
    """Read the supported clients from the catalogue."""

    def __init__(self, catalog: ClientCatalogPort) -> None:
        """Wire the use case to the client catalogue.

        Args:
            catalog: The supported clients and their facts.
        """
        self._catalog = catalog

    def execute(self) -> tuple[ClientInfo, ...]:
        """Return every supported client, in canonical listing order."""
        return self._catalog.supported()
