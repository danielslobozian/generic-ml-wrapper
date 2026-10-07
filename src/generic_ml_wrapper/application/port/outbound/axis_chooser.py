# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""Outbound port: choose a role or environment during first-run setup."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.axis import AxisPrompt, AxisSelection
    from generic_ml_wrapper.common.i18n import Localizer


class AxisChooserPort(ABC):
    """Offer an axis (role/environment) as a menu of examples plus a free-text option."""

    @abstractmethod
    def choose(
        self, prompt: AxisPrompt, default: str, i18n: Localizer | None = None
    ) -> AxisSelection:
        """Return the chosen axis.

        Args:
            prompt: The per-axis wiring (examples + i18n keys).
            default: The slug resolved to off a terminal, or when a typed answer yields
                no slug-worthy content.
            i18n: The localiser for the prompt; ``None`` uses the construction-time one.

        Returns:
            The resolved :class:`AxisSelection` (slug + label + description).
        """
