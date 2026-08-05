# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the pre-launch client-availability check."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.client_readiness import ClientReadiness

if TYPE_CHECKING:
    pass


class CheckClientReadyUseCase(ABC):
    """Report whether a resolved client can launch before the wrapper tries."""

    @abstractmethod
    def execute(self, client: str) -> ClientReadiness:
        """Check a resolved client's availability.

        Args:
            client: The resolved client name (``--client`` or the config default).

        Returns:
            The readiness verdict and the guidance data for an unavailable client.
        """
