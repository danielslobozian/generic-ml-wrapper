# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""``PersonaChooserPort`` that offers a persona on a terminal, declining otherwise."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from generic_ml_wrapper.application.port.outbound.persona_chooser import PersonaChooserPort

if TYPE_CHECKING:
    from generic_ml_wrapper.application.domain.model.persona import Persona


class TtyPersonaChooser(PersonaChooserPort):
    """Offer a persona at an interactive terminal; decline when there is none.

    The prompt is written to stderr and read from stdin; ``Enter`` (or no terminal)
    declines, leaving the companion off — a stranger is never assigned a character.
    """

    def choose(self, personas: list[Persona]) -> str | None:
        """Offer the personas and return the chosen name, or ``None`` to decline.

        Args:
            personas: The selectable personas to offer.

        Returns:
            The chosen persona name, or ``None`` when declined or there is no terminal.
        """
        if not personas or not (sys.stdin.isatty() and sys.stderr.isatty()):
            return None
        print("gmlw: pick a persona (its voice greets you and can shape tone)?", file=sys.stderr)
        for index, persona in enumerate(personas, start=1):
            print(f"  {index}) {persona.name} — {persona.description}", file=sys.stderr)
        while True:
            reply = self._read(f"Pick a number [1-{len(personas)}, Enter to skip]: ")
            if reply is None:
                return None
            reply = reply.strip()
            if not reply:
                return None  # skip -> companion stays off
            if reply.isdigit() and 1 <= int(reply) <= len(personas):
                return personas[int(reply) - 1].name
            print(f"  '{reply}' is not one of 1-{len(personas)}.", file=sys.stderr)

    def _read(self, prompt: str) -> str | None:
        """Read one line for the prompt, or ``None`` at end of input."""
        print(prompt, end="", file=sys.stderr, flush=True)
        line = sys.stdin.readline()
        return None if line == "" else line
