# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The per-client outbound port for parsing a status-line payload."""

from __future__ import annotations

from abc import ABC, abstractmethod

from generic_ml_wrapper.application.domain.model.client_status import ClientStatus


class ClientStatusParserPort(ABC):
    """Parse a client's status-line payload into a client-agnostic ``ClientStatus``.

    Each client pipes a different payload shape, so this is implemented per client.
    """

    @abstractmethod
    def parse(self, payload: dict[str, object]) -> ClientStatus:
        """Parse a client's status payload.

        Args:
            payload: The decoded JSON the client piped to the status-line command.

        Returns:
            The parsed status (fields the client omitted are ``None``).
        """
