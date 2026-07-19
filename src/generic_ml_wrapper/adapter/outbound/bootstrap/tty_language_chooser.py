# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``LanguageChooserPort`` that prompts on a terminal, resolving to the default otherwise."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.tty_prompt import Choice, choose_number
from generic_ml_wrapper.application.port.outbound.language_chooser import LanguageChooserPort

if TYPE_CHECKING:
    from generic_ml_wrapper.common.i18n import Localizer

# Endonyms — a language names itself the same regardless of the UI language, so these
# labels need no translation. Codes without an entry fall back to the bare code.
_ENDONYMS = {"en": "English", "fr": "Français"}


class TtyLanguageChooser(LanguageChooserPort):
    """Ask the user which language gmlw should speak, but only at a terminal.

    Delegates the prompt mechanics to :func:`choose_number`. Because a language must
    always resolve, a non-TTY run (or an unpicked list) falls back to ``default`` rather
    than declining — the rest of the forced init has to have a voice.
    """

    def __init__(self, i18n: Localizer) -> None:
        """Bind the chooser to the seed localiser for its (first-step) prompt text.

        Args:
            i18n: The localiser supplying the header and fixed prompt fragments. This
                runs before a language is chosen, so it speaks the ``$LANG``-seeded one.
        """
        self._i18n = i18n

    def choose(self, languages: list[str], default: str) -> str:
        """Prompt for a language, resolving to ``default`` on an empty line or non-TTY.

        Args:
            languages: The supported language codes to choose among.
            default: The code to resolve to when nothing is picked.

        Returns:
            The chosen code, or ``default`` when there is no terminal to prompt on.
        """
        default_index = languages.index(default) if default in languages else 0
        picked = choose_number(
            self._i18n.t("init.language.header"),
            [Choice(value=code, label=_ENDONYMS.get(code, code)) for code in languages],
            self._i18n,
            default=default_index,
        )
        return picked if picked is not None else default
