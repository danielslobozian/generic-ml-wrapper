# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for persisting what setup decided."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.init_answers import InitAnswers
    from generic_ml_wrapper.application.port.inbound.init_outcome import InitOutcome


class SaveInitAnswersUseCase(ABC):
    """Persist the settled answers and report what the install became.

    All that is left of the old interview use case. Asking, defaulting, re-asking and
    rendering were the terminal's and have gone there; resolving an axis answer to a
    slug and writing the layout were always this layer's.
    """

    @abstractmethod
    def execute(self, answers: InitAnswers) -> InitOutcome:
        """Seed or merge the configuration from ``answers``.

        A brand-new install gets the full layout seeded; an existing one has the answers
        merged into the config it already has, never rewritten over.

        Args:
            answers: The settled answers, as codes.

        Returns:
            What was decided, whether the install was fresh, and any values a merge
            replaced -- so the caller can tell the user what changed under them.
        """
