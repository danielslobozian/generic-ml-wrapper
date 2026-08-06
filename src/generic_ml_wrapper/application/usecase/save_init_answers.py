# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The SaveInitAnswersUseCase use case: persist what setup decided."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.init_outcome import InitOutcome
from generic_ml_wrapper.application.port.inbound.save_init_answers import SaveInitAnswersUseCase
from generic_ml_wrapper.application.port.outbound.init_selections import InitSelections

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.init_answers import InitAnswers
    from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
    from generic_ml_wrapper.application.port.outbound.layout_seeder import LayoutSeederPort


class SaveInitAnswersService(SaveInitAnswersUseCase):
    """Turn the settled answers into a seeded (or merged) installation."""

    def __init__(
        self, *, seeder: LayoutSeederPort, detector: ClientDetectorPort, version: str
    ) -> None:
        """Wire the use case to the seeder and the version it stamps.

        Args:
            seeder: Writes the layout and merges the config.
            detector: Reports the installed clients, echoed back in the outcome.
            version: The gmlw version stamped into the ``[init]`` gate marker.
        """
        self._seeder = seeder
        self._detector = detector
        self._version = version

    def execute(self, answers: InitAnswers) -> InitOutcome:
        """Seed or merge the configuration from ``answers``."""
        persisted = self._seeder.initialize(
            InitSelections(
                version=self._version,
                language=answers.language,
                name=answers.name,
                role=answers.role,
                environment=answers.environment,
                persona=answers.persona,
                client=answers.client,
            )
        )
        return InitOutcome(
            language=answers.language,
            name=answers.name,
            role=answers.role,
            environment=answers.environment,
            persona=answers.persona,
            client=answers.client,
            found=self._detector.available(),
            fresh=persisted.fresh,
            overwrites=persisted.overwrites,
        )
