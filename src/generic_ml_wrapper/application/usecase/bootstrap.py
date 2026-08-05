# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The BootstrapUseCase use case: ensure the runtime layout exists."""

from __future__ import annotations

from generic_ml_wrapper.application.port.inbound.bootstrap import BootstrapUseCase
from generic_ml_wrapper.application.port.outbound.layout_seeder import LayoutSeederPort


class BootstrapService(BootstrapUseCase):
    """Ensure the runtime layout by delegating to a layout seeder."""

    def __init__(self, seeder: LayoutSeederPort) -> None:
        """Wire the use case to its outbound seeder.

        Args:
            seeder: The seeder that creates missing directories and the config.
        """
        self._seeder = seeder

    def execute(self) -> None:
        """Ensure the runtime layout exists (idempotent, missing-only)."""
        self._seeder.ensure()
