# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for the client catalogue: which clients exist and how to run them."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_info import ClientInfo


class ClientCatalogPort(ABC):
    """Outbound port for the supported clients and their environmental facts.

    Install commands, login steps, release-feed URLs and version-probe selectors are
    *environment*, not domain: they change when a vendor changes, on a schedule nobody
    here controls, and adding a client should not mean editing source. They arrive
    through this port so the domain keeps the shape of a client and knows nothing about
    any particular one.
    """

    @abstractmethod
    def supported(self) -> tuple[ClientInfo, ...]:
        """Return every supported client, in canonical listing order."""

    @abstractmethod
    def by_name(self, name: str) -> ClientInfo | None:
        """Return the catalogue entry for a client name, or ``None`` when unsupported.

        Args:
            name: The gmlw client id.

        Returns:
            The matching entry, or ``None``.
        """
