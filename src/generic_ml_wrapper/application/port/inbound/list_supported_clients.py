# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the clients this wrapper knows how to launch."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.client_info import ClientInfo


class ListSupportedClients(ABC):
    """The supported clients and their setup facts, whether installed or not.

    Distinct from listing what is *available*: this is the catalogue itself, used to name
    the valid choices when a run asks for something unsupported, and to show how each one
    is installed when none of them is.
    """

    @abstractmethod
    def execute(self) -> tuple[ClientInfo, ...]:
        """Return every supported client, in canonical listing order."""
