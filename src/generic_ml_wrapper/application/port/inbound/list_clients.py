# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing the supported clients and their install status."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.port.inbound.listed_client import ListedClient


class ListClientsUseCase(ABC):
    """List the supported clients with their install status and version."""

    @abstractmethod
    def execute(self) -> list[ListedClient]:
        """List the supported clients.

        Returns:
            One status per supported client, in catalog order.
        """
