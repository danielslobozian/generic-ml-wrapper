# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for finding out how the running gmlw was installed."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.installation import Installation


class InstallationPort(ABC):
    """Report how the running gmlw was installed."""

    @abstractmethod
    def inspect(self) -> Installation:
        """Return the running gmlw's installation; never raises.

        Returns:
            Its source and manager; a source install when the package metadata cannot
            be found, as when running from an unbuilt checkout.
        """
