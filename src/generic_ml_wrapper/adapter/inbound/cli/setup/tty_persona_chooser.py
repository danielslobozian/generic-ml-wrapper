# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``PersonaChooserPort`` that offers a persona on a terminal, declining otherwise."""

from __future__ import annotations

from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.inbound.cli.setup.tty_prompt import Choice, choose_number

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.inbound.common.i18n.message_source_accessor import (
        MessageSourceAccessor,
    )
    from generic_ml_wrapper.application.domain.model.persona import Persona


class TtyPersonaChooser:
    """Offer a persona at an interactive terminal; decline when there is none.

    The prompt is written to stderr and read from stdin; an empty line (or no terminal)
    declines, leaving the companion off — a stranger is never assigned a character.
    """

    def __init__(self, message_source: MessageSourceAccessor) -> None:
        """Bind the chooser to a message source for its prompt text.

        Args:
            message_source: The message source supplying the header and fixed prompt fragments.
        """
        self._message_source = message_source

    def choose(
        self, personas: list[Persona], message_source: MessageSourceAccessor | None = None
    ) -> str | None:
        """Offer the personas and return the chosen name, or ``None`` to decline.

        Args:
            personas: The selectable personas to offer.
            message_source: The message source for the prompt; ``None`` uses the
                construction-time one.

        Returns:
            The chosen persona name, or ``None`` when declined or there is no terminal.
        """
        message_source = message_source or self._message_source
        return choose_number(
            message_source.get_message("init.persona.header"),
            [
                Choice(value=persona.name, label=persona.name, description=persona.description)
                for persona in personas
            ],
            message_source,
            skippable=True,
        )
