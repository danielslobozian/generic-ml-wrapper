# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for asking which authoring experiences exist."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.authoring_mode import AuthoringMode


class ListAuthoringModesUseCase(ABC):
    """Report the authoring experiences a session can run.

    Named for the set, not for one of its members: ``GUIDED`` is an answer, not the
    question. A port called after one value cannot grow a third without lying.
    """

    @abstractmethod
    def execute(self) -> list[AuthoringMode]:
        """Return every offered authoring mode, in the order they should be presented."""
