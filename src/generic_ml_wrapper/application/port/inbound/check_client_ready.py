# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the pre-launch client-availability check."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_catalog import ClientInfo


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
    """

    client: str
    ready: bool
    missing: ClientInfo | None
    installed: tuple[str, ...]


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
