# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListAuthoringModesUseCase use case: which authoring experiences exist."""

from __future__ import annotations

from generic_ml_wrapper.application.domain.model.authoring_mode import AuthoringMode
from generic_ml_wrapper.application.port.inbound.list_authoring_modes import (
    ListAuthoringModesUseCase,
)


class ListAuthoringModesService(ListAuthoringModesUseCase):
    """Report the authoring modes, in the order they should be offered."""

    def execute(self) -> list[AuthoringMode]:
        """Return every offered authoring mode."""
        return list(AuthoringMode)
