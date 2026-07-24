# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for listing the supported clients and their install status."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ClientStatus:
    """The status of one supported client.

    Attributes:
        name: The gmlw client id (e.g. ``claude``).
        display: The human-readable name (e.g. ``Claude Code``).
        installed: Whether the client's binary is on ``PATH``.
        version: The installed on-disk version, or ``None`` when absent or unreadable.
        resumable: Whether a session on this client can be resumed.
        is_default: Whether this is the configured default client.
    """

    name: str
    display: str
    installed: bool
    version: str | None
    resumable: bool
    is_default: bool


class ListClients(ABC):
    """List the supported clients with their install status and version."""

    @abstractmethod
    def execute(self) -> list[ClientStatus]:
        """List the supported clients.

        Returns:
            One status per supported client, in catalog order.
        """
