# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for asking which authoring experience to run."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.authoring_mode import AuthoringMode


class GuidedChooserPort(ABC):
    """Outbound port for the guided-versus-quick authoring choice.

    Asking is a conversation, and whether there is anyone to ask depends on how the
    wrapper was invoked — so the question, and the decision that there is nobody to
    answer it, both belong outside.
    """

    @abstractmethod
    def choose(self) -> AuthoringMode | None:
        """Return the chosen authoring mode, or ``None`` when nobody can be asked."""
