# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for choosing the parser that understands a client's status."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.client_status import (
        ClientStatusParserPort,
    )


class StatusParsersPort(ABC):
    """Resolve the status parser for a client.

    Which clients exist and how each spells its status is knowledge about the outside
    world, so the choice is made out here rather than by the use case that renders the
    line -- and rather than by whoever invoked it, who would have to know the same thing.
    """

    @abstractmethod
    def for_client(self, client: str | None) -> ClientStatusParserPort:
        """Return the parser for ``client``.

        Args:
            client: The launching client's name, or ``None`` when unknown.

        Returns:
            That client's parser; a sensible default for an unknown or absent name, since
            a status line that cannot identify its client still has to render something.
        """
