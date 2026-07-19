# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The outbound port for choosing the language gmlw speaks, on first run."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LanguageChooserPort(ABC):
    """Ask which supported language gmlw should speak to the user."""

    @abstractmethod
    def choose(self, languages: list[str], default: str) -> str:
        """Pick a language from the supported set.

        Unlike the client/persona choosers, this never returns ``None``: a language is
        always resolved so the rest of the forced pass has a voice. A non-interactive
        run (no terminal) resolves to ``default`` rather than blocking.

        Args:
            languages: The supported language codes to choose among.
            default: The code to fall back to on an empty line or a non-interactive run.

        Returns:
            The chosen language code (always one of ``languages``; ``default`` when
            nothing was picked).
        """
