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


class FirstRunInitUseCase(FirstRunInit):
    """Seed ``~/.gmlw`` with a default client picked from what is installed.

    One client installed → it becomes the default silently. Several → the chooser
    decides (and may decline, e.g. non-interactively). None → the layout is seeded
    without a baked-in default, so the built-in ``claude`` default still applies.
    """

    def __init__(
        self,
        *,
        detector: ClientDetectorPort,
        seeder: LayoutSeederPort,
        chooser: ClientChooserPort,
    ) -> None:
        """Wire the use case to its detector, seeder, and chooser.

        Args:
            detector: Reports which built-in clients are installed.
            seeder: Creates the runtime layout and seeds the config.
            chooser: Resolves the tie when several clients are installed.
        """
        self._detector = detector
        self._seeder = seeder
        self._chooser = chooser

    def execute(self) -> FirstRunOutcome:
        """Detect clients, pick a default, seed the layout, and report the outcome.

        Returns:
            The clients found and the default chosen (``None`` when none was).
        """
        found = self._detector.available()
        if not found:
            chosen = None
        elif len(found) == 1:
            chosen = found[0]
        else:
            chosen = self._chooser.choose(found)
        self._seeder.ensure(default_client=chosen)
        return FirstRunOutcome(found=found, chosen=chosen)
