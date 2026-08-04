# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the pre-launch client-availability check."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_info import ClientInfo


@dataclass(frozen=True)
class ClientReadiness:
    """Whether the resolved client can launch, and what to show when it can't.

    Attributes:
        client: The resolved client name that was checked.
        ready: Whether the client can launch (installed, or a trusted override).
        missing: The catalog entry to install when a supported client is absent;
            ``None`` when ready, or when the client is not a supported built-in.
        installed: The supported clients currently on ``PATH`` (to suggest an
            alternative, or to detect that none are installed at all).
        install_command: How to install ``missing`` on the platform this is running on,
            or ``None`` when nothing is missing. Resolved here rather than by whoever
            renders it: which command suits which platform is a fact the catalogue holds,
            and asking the operating system what it is running on is not the caller's to do.
        catalogue_install_commands: The same, for every supported client, in listing
            order -- what to show when none of them is installed.
    """

    client: str
    ready: bool
    missing: ClientInfo | None
    installed: tuple[str, ...]
    install_command: str | None = None
    catalogue_install_commands: tuple[tuple[str, str], ...] = ()


class CheckClientReady(ABC):
    """Report whether a resolved client can launch before the wrapper tries."""

    @abstractmethod
    def execute(self, client: str) -> ClientReadiness:
        """Check a resolved client's availability.

        Args:
            client: The resolved client name (``--client`` or the config default).

        Returns:
            The readiness verdict and the guidance data for an unavailable client.
        """
