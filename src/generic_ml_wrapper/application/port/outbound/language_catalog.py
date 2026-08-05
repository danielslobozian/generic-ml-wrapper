# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for what languages this build ships."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LanguageCatalogPort(ABC):
    """Report which languages have a shipped catalogue.

    The answer depends on what was packaged into the build, which is exactly the kind
    of fact the application must not read for itself.
    """

    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Return the supported language codes, in canonical order."""

    @abstractmethod
    def default_language(self) -> str:
        """Return the code used when nobody has chosen one."""
