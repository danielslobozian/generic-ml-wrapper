# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The FirstRunInit use case: detect clients, choose a default, seed the layout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.first_run_init import (
    FirstRunInit,
    FirstRunOutcome,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.client_chooser import ClientChooserPort
    from generic_ml_wrapper.application.port.outbound.client_detector import ClientDetectorPort
    from generic_ml_wrapper.application.port.outbound.layout_seeder import LayoutSeederPort
    from generic_ml_wrapper.application.port.outbound.persona_chooser import PersonaChooserPort
    from generic_ml_wrapper.application.port.outbound.persona_source import PersonaSourcePort


class FirstRunInitUseCase(FirstRunInit):
    """Seed ``~/.gmlw`` with a default client and persona picked on first run.

    One client installed → it becomes the default silently. Several → the chooser
    decides (and may decline, e.g. non-interactively). None → the layout is seeded
    without a baked-in default, so the built-in ``claude`` default still applies.
    The user is then offered a persona; declining leaves the companion off.
    """

    def __init__(
        self,
        *,
        detector: ClientDetectorPort,
        seeder: LayoutSeederPort,
        chooser: ClientChooserPort,
        personas: PersonaSourcePort,
        persona_chooser: PersonaChooserPort,
    ) -> None:
        """Wire the use case to its detector, seeder, and choosers.

        Args:
            detector: Reports which built-in clients are installed.
            seeder: Creates the runtime layout and seeds the config.
            chooser: Resolves the tie when several clients are installed.
            personas: The source the offered personas come from.
            persona_chooser: Offers the persona choice (declines non-interactively).
        """
        self._detector = detector
        self._seeder = seeder
        self._chooser = chooser
        self._personas = personas
        self._persona_chooser = persona_chooser

    def execute(self) -> FirstRunOutcome:
        """Detect clients, pick a default and a persona, seed, and report the outcome.

        Returns:
            The clients found, the default chosen, and the persona chosen (each
            ``None`` when nothing was picked).
        """
        found = self._detector.available()
        if not found:
            chosen = None
        elif len(found) == 1:
            chosen = found[0]
        else:
            chosen = self._chooser.choose(found)
        persona = self._persona_chooser.choose(self._personas.available())
        self._seeder.ensure(default_client=chosen, persona=persona)
        return FirstRunOutcome(found=found, chosen=chosen, persona=persona)
