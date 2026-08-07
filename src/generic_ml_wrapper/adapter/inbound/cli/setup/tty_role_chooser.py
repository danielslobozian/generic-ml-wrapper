# SPDX-FileCopyrightText: 2026 Daniel Slobozian
# SPDX-License-Identifier: Apache-2.0
"""The role step of the forced init, at a terminal.

Rather than a bare free-text box — which produced folders full of spaces, capitals and
accents — this shows a short concept blurb, offers the packaged starting points, and adds a
"type your own" option. A typed answer keeps the human wording as the label and description
but is reduced to a clean kebab-case code for the folder and config value, and the code is
echoed back so the mapping is never a surprise. A non-TTY run declines to the supplied
default, so automation never blocks.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from generic_ml_wrapper.adapter.inbound.cli.setup.tty_prompt import Choice, choose_number, emit
from generic_ml_wrapper.application.domain.model.role import Role
from generic_ml_wrapper.application.domain.model.uncodable_role_label_error import (
    UncodableRoleLabelError,
)

if TYPE_CHECKING:
    from generic_ml_wrapper.adapter.inbound.cli.setup.message_source import MessageSource
    from generic_ml_wrapper.application.port.inbound.list_role_examples import (
        ListRoleExamplesUseCase,
    )

# Sentinel option value: "type a role other than the offered examples".
_TYPE_YOUR_OWN = "\x00type-your-own"
_INTRO = "init.role.intro"
_HEADER = "init.role.header"
_TYPE_YOUR_OWN_KEY = "init.role.type_your_own"
_PROMPT = "init.role.prompt"
_SAVED = "init.role.saved"


class TtyRoleChooser:
    """Guide the role choice at an interactive terminal."""

    def __init__(self, i18n: MessageSource, examples: ListRoleExamplesUseCase) -> None:
        """Bind the chooser to a localiser and the roles it offers.

        Args:
            i18n: The default localiser for the blurb, menu, and echo.
            examples: Supplies the offered starting-point roles.
        """
        self._i18n = i18n
        self._examples = examples

    def choose(self, default: str, i18n: MessageSource | None = None) -> Role:
        """Offer the examples plus "type your own"; return the chosen role.

        Args:
            default: The code used off a terminal, or when a typed answer yields none.
            i18n: The localiser to use; ``None`` falls back to the construction-time one.

        Returns:
            The chosen role.
        """
        loc = i18n or self._i18n
        offered = self._examples.execute()
        emit(loc.t(_INTRO))
        choices = [
            Choice(value=role.code, label=loc.t(role.label), description=loc.t(role.description))
            for role in offered
        ]
        choices.append(Choice(value=_TYPE_YOUR_OWN, label=loc.t(_TYPE_YOUR_OWN_KEY)))
        picked = choose_number(loc.t(_HEADER), choices, loc, default=0)
        if picked is None:  # non-TTY, EOF — decline to the default
            return Role(default, default, default)
        if picked != _TYPE_YOUR_OWN:
            chosen = next(role for role in offered if role.code == picked)
            return Role(chosen.code, loc.t(chosen.label), loc.t(chosen.description))
        return self._type_your_own(default, loc)

    def _type_your_own(self, default: str, loc: MessageSource) -> Role:
        """Read a free-text answer, keep it as the label, and derive + echo its code."""
        typed = self._read(loc.t(_PROMPT))
        if typed is None or not typed.strip():
            return Role(default, default, default)
        label = typed.strip()
        try:
            role = Role(None, label, label)
        except UncodableRoleLabelError:
            # Nothing codeable in what they typed; keep the default rather than refuse a
            # setup step the user cannot skip.
            return Role(default, default, default)
        emit(loc.t(_SAVED, code=role.code))
        return role

    @staticmethod
    def _read(prompt_text: str) -> str | None:
        """Write ``prompt_text`` to stderr and read one line from stdin, or ``None`` off a TTY."""
        if not (sys.stdin.isatty() and sys.stderr.isatty()):
            return None
        print(prompt_text, end="", file=sys.stderr, flush=True)
        line = sys.stdin.readline()
        return None if line == "" else line
