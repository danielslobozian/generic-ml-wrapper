# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The RenderFarewellUseCase use case: say goodbye, if there is anyone to say it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.render_farewell import RenderFarewellUseCase

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.service.localizer import Localizer
    from generic_ml_wrapper.application.port.inbound.application_settings import (
        ApplicationSettingsUseCase,
    )
    from generic_ml_wrapper.application.port.outbound.system_info import SystemInfoPort


class RenderFarewellService(RenderFarewellUseCase):
    """Compose the parting line, falling back to the account name when none is set."""

    def __init__(
        self,
        settings: ApplicationSettingsUseCase,
        system: SystemInfoPort,
        localizer: Localizer,
    ) -> None:
        """Wire the use case to the companion's settings and the host's account name.

        Args:
            settings: Whether a companion is configured, and what it calls the user.
            system: Where the account name comes from when the user has not given one.
            localizer: Renders the line in the language the wrapper is speaking.
        """
        self._settings = settings
        self._system = system
        self._localizer = localizer

    def execute(self) -> str | None:
        """Return the parting line, or ``None`` when no companion is configured."""
        companion = self._settings.companion()
        if companion.persona is None:
            return None
        return self._localizer.t("farewell", name=companion.name or self._system.username())
