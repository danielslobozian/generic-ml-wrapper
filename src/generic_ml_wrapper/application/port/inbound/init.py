# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for the forced first-run init: the ordered setup interview."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.init_outcome import InitOutcome

if TYPE_CHECKING:
    pass


class InitUseCase(ABC):
    """Run the forced first-run setup: language → name → role → environment → persona → client."""

    @abstractmethod
    def execute(self) -> InitOutcome:
        """Run the ordered interview, persist the result, and report what it decided.

        Returns:
            The outcome of the interview.
        """
