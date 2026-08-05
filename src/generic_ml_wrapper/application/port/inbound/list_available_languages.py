# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The inbound port for asking which languages this build can speak."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ListAvailableLanguagesUseCase(ABC):
    """Report the language codes this build ships catalogues for.

    Which languages exist is a fact about what is installed, so it is read through an
    outbound port; asking it is a query, so it arrives here. The terminal renders each
    code as its own endonym -- ``English``, ``Français`` -- because a language menu is
    the one menu that cannot be translated: the reader has not chosen a language yet.
    """

    @abstractmethod
    def execute(self) -> list[str]:
        """Return the supported language codes, in canonical order."""
