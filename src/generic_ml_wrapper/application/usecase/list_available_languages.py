# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The ListAvailableLanguagesUseCase use case: which languages this build speaks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.inbound.list_available_languages import (
    ListAvailableLanguagesUseCase,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.application.port.outbound.language_catalog import LanguageCatalogPort


class ListAvailableLanguagesService(ListAvailableLanguagesUseCase):
    """Report the shipped language codes, read through the catalogue that holds them."""

    def __init__(self, catalog: LanguageCatalogPort) -> None:
        """Wire the use case to the catalogue.

        Args:
            catalog: Reports which languages have a catalogue in this build.
        """
        self._catalog = catalog

    def execute(self) -> list[str]:
        """Return the supported language codes, in canonical order."""
        return self._catalog.supported_languages()
