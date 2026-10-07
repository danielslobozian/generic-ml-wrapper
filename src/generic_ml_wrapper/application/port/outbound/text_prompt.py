# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for a free-text first-run answer (name, role, environment)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.common.i18n import Localizer


class TextPromptPort(ABC):
    """Ask a single free-text question with a default, declining to it off a terminal."""

    @abstractmethod
    def ask(self, header: str, default: str, i18n: Localizer | None = None) -> str:
        """Ask ``header`` and return the typed answer, or ``default``.

        Never returns ``None`` or an empty string: a forced pass must always resolve a
        value. An empty line or a non-interactive run (no terminal) yields ``default``.

        Args:
            header: The already-localised question line.
            default: The value used on an empty line or a non-interactive run.
            i18n: The localiser for the fixed ``[default …]`` fragment; ``None`` uses the
                prompt's construction-time one.

        Returns:
            The trimmed answer, or ``default`` when nothing was typed.
        """
