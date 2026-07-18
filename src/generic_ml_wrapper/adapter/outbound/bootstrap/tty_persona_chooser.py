# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``PersonaChooserPort`` that offers a persona on a terminal, declining otherwise."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.outbound.bootstrap.tty_prompt import Choice, choose_number
from generic_ml_wrapper.application.port.outbound.persona_chooser import PersonaChooserPort

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.persona import Persona
    from generic_ml_wrapper.common.i18n import Localizer


class TtyPersonaChooser(PersonaChooserPort):
    """Offer a persona at an interactive terminal; decline when there is none.

    The prompt is written to stderr and read from stdin; an empty line (or no terminal)
    declines, leaving the companion off — a stranger is never assigned a character.
    """

    def __init__(self, i18n: Localizer) -> None:
        """Bind the chooser to a localiser for its prompt text.

        Args:
            i18n: The localiser supplying the header and fixed prompt fragments.
        """
        self._i18n = i18n

    def choose(self, personas: list[Persona]) -> str | None:
        """Offer the personas and return the chosen name, or ``None`` to decline.

        Args:
            personas: The selectable personas to offer.

        Returns:
            The chosen persona name, or ``None`` when declined or there is no terminal.
        """
        return choose_number(
            self._i18n.t("init.persona.header"),
            [
                Choice(value=persona.name, label=persona.name, description=persona.description)
                for persona in personas
            ],
            self._i18n,
            skippable=True,
        )
